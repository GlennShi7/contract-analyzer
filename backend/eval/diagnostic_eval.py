"""Explicitly bounded one-shot runner for the four newly authorized diagnostic inputs."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
CASE_IDS = ("belongings_a", "belongings_b", "interest_fact_a", "interest_fact_b")
HARD_LIMIT = 8


def save_json(path, value):
    temporary = path.with_suffix(".writing")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


class BudgetExhausted(RuntimeError):
    pass


class CountedCompletions:
    def __init__(self, underlying, ledger, save):
        self.underlying = underlying
        self.ledger = ledger
        self.save = save

    def create(self, **kwargs):
        if len(self.ledger["requests"]) >= HARD_LIMIT:
            raise BudgetExhausted("No further provider request permitted")
        record = {"case_id": self.ledger["current_case"], "status": "started",
                  "phase": self.ledger.get("current_phase", "baseline"),
                  "started_at_utc": datetime.now(timezone.utc).isoformat()}
        self.ledger["requests"].append(record)
        self.save()  # Persist before any SDK/network call; failed requests count too.
        try:
            response = self.underlying.create(**kwargs)
        except Exception as error:
            record.update(status="failed", failure_type=type(error).__name__, http_status=getattr(error, "status_code", None))
            self.save()
            raise
        record.update(status="completed", model=response.model,
                      usage=response.usage.model_dump() if response.usage else None,
                      choices=[{"finish_reason": choice.finish_reason, "content": choice.message.content}
                               for choice in response.choices])
        self.save()
        return response


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="make the explicitly authorized billable calls")
    parser.add_argument("--output", type=Path, required=True, help="new durable ledger path; existing files are refused")
    parser.add_argument("--follow-up", action="store_true", help="one follow-up round using the SAME cumulative eight-request ledger")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.path.insert(0, str(REPO / "backend"))
    from eval.reasoning_review import load_sources, validate_cases
    dataset = json.loads((REPO / "backend/eval/reasoning_cases.json").read_text(encoding="utf-8"))
    validate_cases(dataset, load_sources(REPO))
    cases_by_id = {case["id"]: case for case in dataset["cases"]}
    cases = [cases_by_id[key] for key in CASE_IDS]
    if not args.live:
        print(json.dumps({"selected_ids": list(CASE_IDS), "hard_limit": HARD_LIMIT,
                          "provider_requests": 0, "mode": "prepare_only"}))
        return
    if args.output.exists() and not args.follow_up:
        parser.error("Output ledger already exists; refusing a repeat batch")
    if args.follow_up and not args.output.exists():
        parser.error("Follow-up requires the existing ledger; it cannot start a fresh allowance")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    from analyzer import analyze_contract, AnalysisOutputError, model_name
    from main import get_llm_client
    from openai import OpenAIError
    if args.follow_up:
        ledger = json.loads(args.output.read_text(encoding="utf-8"))
        if (ledger.get("max_requests") != HARD_LIMIT or len(ledger.get("requests", [])) != 4
                or ledger.get("status") != "completed" or "follow_up" in ledger or ledger["cases"] != cases
                or {r["case_id"] for r in ledger["rows"] if r["status"] == "validated"} != set(CASE_IDS)):
            parser.error("Follow-up requires exactly the completed four-request baseline, unchanged inputs, and no prior follow-up")
        ledger["baseline_finished_at_utc"] = ledger["finished_at_utc"]
        ledger["follow_up"] = {"analyzer_sha256": sha256((REPO / "backend/analyzer.py").read_bytes()).hexdigest(),
                               "started_at_utc": datetime.now(timezone.utc).isoformat(), "rows": []}
        ledger["current_phase"] = "follow_up"
        ledger["status"] = "running"
        rows = ledger["follow_up"]["rows"]
    else:
        ledger = {"status": "running", "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "authorization": "New explicit approval: at most 8 requests including corrections for four selected diagnostic inputs; old remaining 3-request allowance is separate and unused.",
              "max_requests": HARD_LIMIT, "model": model_name(), "cases": cases,
              "analyzer_sha256": sha256((REPO / "backend/analyzer.py").read_bytes()).hexdigest(),
              "law_library_sha256": sha256((REPO / "backend/laws/tenancy_us_il_urbana.json").read_bytes()).hexdigest(),
              "requests": [], "rows": [], "metrics": None,
                  "limitations": "Post-error synthetic diagnostics with draft source-based criteria; no independent legal adjudication, general accuracy or recall score."}
        rows = ledger["rows"]
    save = lambda: save_json(args.output, ledger)
    save()
    raw_client = get_llm_client()
    require_no_retries = getattr(raw_client, "max_retries", None)
    if require_no_retries != 0:
        raise RuntimeError("SDK retries must be zero before billable evaluation")
    counted = CountedCompletions(raw_client.chat.completions, ledger, save)
    client = SimpleNamespace(chat=SimpleNamespace(completions=counted))
    for case in cases:
        ledger["current_case"] = case["id"]
        try:
            result = analyze_contract(case["contract_text"], client, jurisdiction="us_il_urbana")
        except AnalysisOutputError as error:
            rows.append({"case_id": case["id"], "status": "failed", "failure_type": type(error).__name__})
            save()
            print(case["id"], "failed validation; diagnostics retained", flush=True)
            continue
        except (BudgetExhausted, OpenAIError) as error:
            rows.append({"case_id": case["id"], "status": "failed", "failure_type": type(error).__name__,
                                   "http_status": getattr(error, "status_code", None)})
            save()
            break
        rows.append({"case_id": case["id"], "status": "validated", "result": result.model_dump(mode="json")})
        save()
        print(case["id"], f"validated; attempts={result.attempts}; requests_total={len(ledger['requests'])}", flush=True)
    ledger["status"] = "completed" if len(rows) == len(cases) and all(row["status"] == "validated" for row in rows) else "partial_or_failed"
    ledger["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    ledger["unrun_cases"] = [key for key in CASE_IDS if key not in {record["case_id"] for record in ledger["requests"] if record.get("phase", "baseline") == ledger.get("current_phase", "baseline")}]
    save()
    print(json.dumps({"status": ledger["status"], "requests": len(ledger["requests"]), "unrun_cases": ledger["unrun_cases"]}))
    print("Saved", args.output)


if __name__ == "__main__":
    main()

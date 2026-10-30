"""Prepare or explicitly run the synthetic completion check; no accuracy claims."""
import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

from analyzer import AnalysisOutputError, analyze_contract, model_name
from eval.reasoning_review import load_sources, validate_cases

REPO = Path(__file__).resolve().parents[2]
MAX_REQUESTS = 76
DIMENSIONS = ("contract_facts", "scope_and_facts", "conditions_and_exceptions", "legal_support",
              "false_positive", "expected_issue_coverage", "uncertainty_and_consistency")


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def build_plan(root=REPO):
    root = Path(root)
    cases = json.loads((root / "backend/eval/reasoning_cases.json").read_text(encoding="utf-8"))
    validate_cases(cases, load_sources(root))
    inputs = [{"id": case["id"], "kind": "diagnostic", "jurisdiction": case["jurisdiction"],
               "text": case["contract_text"], "pair_id": case["pair_id"], "variant": case["variant"], "draft_criterion": case["criterion"],
               "must_not_infer": case["must_not_infer"], "source_anchors": case["source_anchors"]}
              for case in cases["cases"]]
    for name in ("lease_zh", "labor_zh", "lease_en"):
        inputs.append({"id": name, "kind": "full_contract", "jurisdiction": "cn" if name.endswith("_zh") else "us_il_urbana",
                       "text": (root / f"backend/eval/contracts/{name}.txt").read_text(encoding="utf-8"),
                       "draft_criterion": None, "must_not_infer": [], "source_anchors": []})
    files = ["backend/analyzer.py", "backend/eval/acceptance_eval.py", "backend/eval/reasoning_cases.json",
             "backend/laws/labor.json", "backend/laws/tenancy.json", "backend/laws/tenancy_us_il_urbana.json"]
    plan = {"schema_version": 1, "model": model_name(), "repetitions": 2, "max_requests": MAX_REQUESTS,
            "inputs": inputs, "text_fingerprints": {name: sha256((root / name).read_text(encoding="utf-8").encode()).hexdigest() for name in files},
            "rows": [{"id": f"{case['id']}:r{repeat}", "input_id": case["id"], "repeat": repeat}
                     for repeat in (1, 2) for case in inputs],
            "limitations": "Existing synthetic inputs and post-error diagnostic drafts, two samples each; not held-out, independently adjudicated, legal accuracy, recall, or a proof of stability."}
    plan["fingerprint"] = digest(plan)
    return plan


def save(path, value):
    temporary = path.with_suffix(".writing")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


@contextmanager
def exclusive(directory):
    # An abandoned lock deliberately fails closed; never reset a fee counter automatically.
    lock = directory / "active.lock"
    handle = lock.open("x", encoding="utf-8")
    try:
        handle.write(now())
        handle.close()
        yield
    finally:
        handle.close()
        lock.unlink()


class BudgetExhausted(RuntimeError):
    pass


class CountedCompletions:
    def __init__(self, underlying, ledger, persist):
        self.underlying, self.ledger, self.persist = underlying, ledger, persist

    def create(self, **kwargs):
        if len(self.ledger["requests"]) >= self.ledger["plan"]["max_requests"]:
            raise BudgetExhausted("Cumulative request limit reached")
        record = {"row_id": self.ledger["current_row"], "status": "started", "started_at_utc": now(),
                  "payload": deepcopy(kwargs)}
        self.ledger["requests"].append(record)
        self.persist()  # Includes failed and interrupted sends; save before touching the SDK.
        try:
            response = self.underlying.create(**kwargs)
        except BaseException as error:
            record.update(status="failed", failure_type=type(error).__name__, http_status=getattr(error, "status_code", None))
            self.persist()
            raise
        record.update(status="completed", model=response.model, usage=response.usage.model_dump() if response.usage else None,
                      choices=[{"finish_reason": choice.finish_reason, "content": choice.message.content} for choice in response.choices])
        self.persist()
        return response


def worksheet(ledger):
    completed = {row["id"]: row for row in ledger["rows"]}
    return {"status": "unreviewed", "independent_adjudication": False, "plan_fingerprint": ledger["plan"]["fingerprint"],
            "ledger_fingerprint": digest(ledger),
            "legal_accuracy": None, "risk_recall": None,
            "instructions": "Fill each dimension with supported/failed/unknown/not_applicable and exact output/source evidence. Record reviewer role, second review and resolution. Never treat unreviewed or missing output as passed.",
            "rows": [{**row, "generation_status": completed.get(row["id"], {}).get("status", "not_run"),
                      "reviewer": None, "reviewer_role": None, "independent_second_review": None, "resolution": None,
                      "dimensions": {key: {"verdict": "unreviewed", "output_pointer": None, "output_quote": None,
                                           "source_anchors": [], "rationale": None} for key in DIMENSIONS}}
                     for row in ledger["plan"]["rows"]]}


def summary(ledger):
    rows = {row["id"]: row for row in ledger["rows"]}
    return {"status": ledger["status"], "plan_fingerprint": ledger["plan"]["fingerprint"],
            "provider_requests": len(ledger["requests"]), "generation_rows": len(ledger["plan"]["rows"]),
            "validated_rows": sum(row["status"] == "validated" for row in rows.values()),
            "unrun_rows": [spec["id"] for spec in ledger["plan"]["rows"] if spec["id"] not in rows],
            "legal_accuracy": None, "risk_recall": None, "stability_accepted": False,
            "comparisons": [{"input_id": item["id"], "draft_criterion": item.get("draft_criterion"),
                             "repeats": [{"id": spec["id"], "status": rows.get(spec["id"], {}).get("status", "not_run"),
                                          "risk_score": rows.get(spec["id"], {}).get("result", {}).get("risk_score"),
                                          "card_titles": [card["title"] for card in rows.get(spec["id"], {}).get("result", {}).get("cards", [])]}
                                         for spec in ledger["plan"]["rows"] if spec["input_id"] == item["id"]]}
                            for item in ledger["plan"]["inputs"]],
            "note": "Generation validity and repeat differences only. Two runs do not establish legal accuracy or stable performance; manual review remains uncompleted."}


def run_batch(ledger, raw_client, persist, analyze=analyze_contract):
    if getattr(raw_client, "max_retries", None) != 0:
        raise ValueError("SDK retries must be zero")
    counted = CountedCompletions(raw_client.chat.completions, ledger, persist)
    client = SimpleNamespace(chat=SimpleNamespace(completions=counted))
    inputs = {item["id"]: item for item in ledger["plan"]["inputs"]}
    # An interrupted attempt is not regenerated on resume: its outcome and billing may be uncertain.
    for row in ledger["rows"]:
        if row["status"] == "pending":
            row.update(status="interrupted", failure_type="InterruptedPreviousProcess")
    done = {row["id"] for row in ledger["rows"]}
    ledger["status"] = "running"
    persist()
    for spec in ledger["plan"]["rows"]:
        if spec["id"] in done:
            continue
        if len(ledger["requests"]) >= ledger["plan"]["max_requests"]:
            break
        item = inputs[spec["input_id"]]
        row = {**spec, "status": "pending"}
        ledger["rows"].append(row)
        ledger["current_row"] = row["id"]
        persist()
        try:
            result = analyze(item["text"], client, jurisdiction=item["jurisdiction"], model=ledger["plan"]["model"])
        except AnalysisOutputError:
            row.update(status="failed", failure_type="AnalysisOutputError")
        except BaseException as error:
            row.update(status="failed", failure_type=type(error).__name__)
            ledger["status"] = "partial_or_failed"
            persist()
            raise
        else:
            row.update(status="validated", result=result.model_dump(mode="json"))
        persist()
    ledger["status"] = "completed" if len(ledger["rows"]) == len(ledger["plan"]["rows"]) and all(row["status"] == "validated" for row in ledger["rows"]) else "partial_or_failed"
    ledger["finished_at_utc"] = now()
    persist()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new directory for plan, cumulative ledger and review template")
    parser.add_argument("--live", action="store_true", help="billable: requires new user approval, not the exhausted historical allowances")
    parser.add_argument("--resume", action="store_true", help="continue the SAME immutable plan and cumulative ledger")
    args = parser.parse_args()
    plan = build_plan()
    directory = args.output.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    with exclusive(directory):
        plan_path, ledger_path = directory / "plan.json", directory / "ledger.json"
        if args.resume:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            if ledger["plan"] != plan or json.loads(plan_path.read_text(encoding="utf-8")) != plan:
                parser.error("Plan/code/source/model changed; refusing to resume")
            if len(ledger["requests"]) > plan["max_requests"]:
                parser.error("Invalid cumulative request ledger")
        else:
            if plan_path.exists() or ledger_path.exists():
                parser.error("Existing plan/ledger refused; use --resume without resetting the allowance")
            ledger = {"status": "prepared", "plan": plan, "requests": [], "rows": [], "created_at_utc": now(),
                      "legal_accuracy": None, "risk_recall": None}
            save(plan_path, plan)
            save(ledger_path, ledger)
        if args.live:
            from main import get_llm_client
            # Only explicitly requested live runs load credentials/create a network client.
            try:
                run_batch(ledger, get_llm_client(), lambda: save(ledger_path, ledger))
            finally:
                save(directory / "review-template.json", worksheet(ledger))
                save(directory / "comparison.json", summary(ledger))
        elif not (directory / "review-template.json").exists():
            save(directory / "review-template.json", worksheet(ledger))
            save(directory / "comparison.json", summary(ledger))
        print(json.dumps({"mode": "live" if args.live else "prepare_only", "status": ledger["status"],
                          "inputs": len(plan["inputs"]), "planned_generations": len(plan["rows"]),
                          "max_requests_including_corrections": plan["max_requests"],
                          "provider_requests_recorded": len(ledger["requests"]), "fingerprint": plan["fingerprint"]}))


if __name__ == "__main__":
    main()

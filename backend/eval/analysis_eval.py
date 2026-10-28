"""Opt-in live structured-analysis check on the three synthetic contracts."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="enable billable DeepSeek requests for selected synthetic fixtures")
    parser.add_argument("--contracts", nargs="+", choices=("lease_zh", "labor_zh", "lease_en"), default=["lease_zh", "labor_zh", "lease_en"])
    parser.add_argument("--english-jurisdiction", choices=("unknown", "us_il_urbana"), default="unknown")
    parser.add_argument("--max-requests", type=int, choices=range(1, 7), default=6, help="hard limit including correction attempts and failed requests")
    args = parser.parse_args()
    if not args.live:
        parser.error("Pass --live explicitly to enable API requests; no requests were made.")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    from analyzer import analyze_contract, model_name
    from analyzer import AnalysisOutputError
    from main import get_llm_client
    from openai import OpenAIError
    client = get_llm_client()
    requests = []

    def complete(**kwargs):
        if len(requests) >= args.max_requests:
            raise RuntimeError("Explicit live-request limit reached; no further request sent.")
        record = {"status": "started"}
        requests.append(record)
        response = client.chat.completions.create(**kwargs)
        record.update(status="completed", model=response.model, usage=response.usage.model_dump() if response.usage else None)
        return response

    counted = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=complete)))
    rows = []
    for name in dict.fromkeys(args.contracts):
        text = (HERE / "contracts" / f"{name}.txt").read_text(encoding="utf-8")
        jurisdiction = "cn" if name.endswith("_zh") else args.english_jurisdiction
        try:
            report = analyze_contract(text, counted, jurisdiction=jurisdiction)
        except (OpenAIError, AnalysisOutputError, RuntimeError) as error:
            raise SystemExit(f"Live verification failed: {type(error).__name__}, HTTP {getattr(error, 'status_code', None)}; no metrics saved.") from None
        rows.append({"contract": name, "text_sha256": sha256(text.encode()).hexdigest(),
                     "jurisdiction": jurisdiction, "result": report.model_dump(mode="json")})
        metrics = report.grounding
        print(f"{name}: cards={metrics.cards_total}, verified_quotes={metrics.cards_verified}, "
              f"allowed_law_ids={metrics.law_references_valid}/{metrics.law_references_total}, attempts={report.attempts}")

    metrics = [row["result"]["grounding"] for row in rows]
    cards = sum(item["cards_total"] for item in metrics)
    verified = sum(item["cards_verified"] for item in metrics)
    references = sum(item["law_references_total"] for item in metrics)
    valid = sum(item["law_references_valid"] for item in metrics)
    result = {
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(), "model": model_name(),
        "analyzer_sha256": sha256((HERE.parent / "analyzer.py").read_bytes()).hexdigest(),
        "dataset": "selected existing synthetic evaluation contracts; not real signed contracts",
        "selected_contracts": list(dict.fromkeys(args.contracts)), "max_requests": args.max_requests,
        "law_sources_sha256": sha256((HERE.parent / "laws/SOURCES.json").read_bytes()).hexdigest(),
        "urbana_law_sources_sha256": sha256((HERE.parent / "laws/SOURCES_US_URBANA.json").read_bytes()).hexdigest(),
        "summary": {"contracts": len(rows), "requests": len(requests), "cards": cards,
                    "verified_quotes": verified, "quote_verification_rate": verified / cards if cards else None,
                    "law_references": references, "valid_law_references": valid,
                    "law_reference_validity_rate": valid / references if references else None},
        "limitations": "Checks quote matching and injected-ID membership before filtering; does not validate legal applicability, analysis correctness, risk scores, or recall.",
        "requests": requests, "rows": rows,
    }
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    path = out / f"analysis_{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))
    print("Saved", path.relative_to(HERE.parent))


if __name__ == "__main__":
    main()

"""Replay and verify a saved completion batch offline, without a provider client."""
import argparse
from collections import Counter
import json
from pathlib import Path
from types import SimpleNamespace

from analyzer import analyze_contract
from eval.acceptance_eval import REPO, build_plan, digest
from eval.reasoning_review import read_pointer, require


def validate_ledger(ledger, root=REPO):
    plan = ledger["plan"]
    require(plan == build_plan(root), "Code, sources, model or plan differ from the saved snapshot")
    require(ledger["status"] in {"prepared", "running", "completed", "partial_or_failed"}, "Unknown batch status")
    require(len(ledger["requests"]) <= plan["max_requests"], "Cumulative request cap exceeded")
    specs = {spec["id"]: spec for spec in plan["rows"]}
    inputs = {item["id"]: item for item in plan["inputs"]}
    rows = {row["id"]: row for row in ledger["rows"]}
    require(len(rows) == len(ledger["rows"]), "Duplicate generation row")
    requests = {}
    for record in ledger["requests"]:
        require(record["row_id"] in rows, "Request has no generation row")
        require(record["status"] in {"started", "completed", "failed"}, "Unknown request status")
        requests.setdefault(record["row_id"], []).append(record)
    validated = cards = references = 0
    for row in rows.values():
        require(row["id"] in specs and all(row[key] == value for key, value in specs[row["id"]].items()), "Unknown or changed row")
        require(row["status"] in {"pending", "validated", "failed", "interrupted"}, "Unknown row status")
        records = requests.get(row["id"], [])
        require(len(records) <= 2, "Generation exceeds one correction")
        if row["status"] != "validated":
            continue
        require(bool(records) and all(r["status"] == "completed" for r in records), "Accepted result lacks completed requests")
        cursor = iter(records)
        replayed = []
        def complete(**kwargs):
            record = next(cursor)
            require(record["payload"] == kwargs, "Request differs from frozen production prompt/input/settings")
            replayed.append(record)
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason=c["finish_reason"], message=SimpleNamespace(content=c["content"])) for c in record["choices"]])
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=complete)))
        item = inputs[row["input_id"]]
        result = analyze_contract(item["text"], client, jurisdiction=item["jurisdiction"], model=plan["model"])
        require(len(replayed) == len(records), "Unexplained extra request")
        require(result.model_dump(mode="json") == row["result"], "Saved report differs from raw-response replay")
        validated += 1
        cards += result.grounding.cards_total
        references += result.grounding.law_references_total
    if ledger["status"] == "completed":
        require(validated == len(plan["rows"]), "Completed status conceals missing/failed generations")
    usage = Counter()
    for record in ledger["requests"]:
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            usage[key] += (record.get("usage") or {}).get(key, 0)
    return {"status": ledger["status"], "ledger_fingerprint": digest(ledger), "provider_requests_recorded": len(ledger["requests"]),
            "offline_provider_requests": 0, "replayed_accepted_reports": validated, "verified_card_quotes": cards,
            "references_in_accepted_reports": references, "usage_including_corrections": dict(usage),
            "legal_accuracy": None, "risk_recall": None, "independent_adjudication": False,
            "note": "Offline replay verifies provenance and production validation only, not the truth or legal support of any explanation."}


def validate_findings(review, ledger):
    require(review["ledger_fingerprint"] == digest(ledger), "Reviewed ledger changed")
    require(review["independent_adjudication"] is False, "This engineering review has no independent adjudication")
    inputs = {item["id"]: item for item in ledger["plan"]["inputs"]}
    sources = {law["id"]: law for name in ("labor.json", "tenancy.json", "tenancy_us_il_urbana.json")
               for law in json.loads((REPO / "backend/laws" / name).read_text(encoding="utf-8"))}
    ids = set()
    for finding in review["findings"]:
        require(finding["id"] not in ids, "Duplicate finding")
        ids.add(finding["id"])
        require(finding["verdict"] in {"supported_observation", "failed", "unknown"}, "Unknown engineering verdict")
        require(bool(finding["rationale"].strip()) and bool(finding["output_evidence"]), "Missing rationale/evidence")
        for evidence in finding["output_evidence"]:
            value = read_pointer(ledger, evidence["pointer"])
            require(isinstance(value, str) and bool(evidence["quote"]) and evidence["quote"] in value, "Output evidence absent")
        for anchor in finding.get("source_anchors", []):
            source = sources[anchor["law_id"]]
            require(source["text_sha256"] == anchor["text_sha256"] and bool(anchor["quote"].strip()) and anchor["quote"] in source["text"], "Source evidence absent/changed")
        for anchor in finding.get("input_evidence", []):
            require(bool(anchor["quote"]) and anchor["quote"] in inputs[anchor["input_id"]]["text"], "Input evidence absent")
    return {"evidence_anchored_findings": len(ids), "legal_accuracy": None, "risk_recall": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--review", type=Path)
    args = parser.parse_args()
    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    result = validate_ledger(ledger)
    if args.review:
        result["review"] = validate_findings(json.loads(args.review.read_text(encoding="utf-8")), ledger)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

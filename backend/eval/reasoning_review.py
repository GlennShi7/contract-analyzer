"""Validate local review evidence; never generate, call a provider, or infer legal accuracy."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def resolve_local(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    require(path.is_relative_to(root), "Evidence path escapes repository")
    return path


def load_sources(root):
    rows = load_json(Path(root) / "backend/laws/tenancy_us_il_urbana.json")
    sources = {}
    for row in rows:
        require(row["id"] not in sources, "Duplicate source ID")
        require(sha256(row["text"].encode()).hexdigest() == row["text_sha256"], "Source checksum mismatch")
        sources[row["id"]] = row
    return sources


def validate_anchors(anchors, sources):
    require(bool(anchors), "At least one source anchor is required")
    for anchor in anchors:
        require(anchor["law_id"] in sources, "Unknown source ID")
        source = sources[anchor["law_id"]]
        require(anchor["text_sha256"] == source["text_sha256"], "Review source has changed")
        require(bool(anchor["quote"].strip()) and anchor["quote"] in source["text"], "Source quote missing")


def validate_cases(data, sources):
    require(data["schema_version"] == 1 and data["label_status"] == "draft_source_based", "Unexpected case schema/status")
    require(data["model_runs"] == [], "This dataset must not imply unperformed model runs")
    ids = set()
    pairs = {}
    for case in data["cases"]:
        require(case["id"] not in ids, "Duplicate case ID")
        ids.add(case["id"])
        require(case["variant"] in {"a", "b"}, "Unknown case variant")
        variants = pairs.setdefault(case["pair_id"], set())
        require(case["variant"] not in variants, "Duplicate pair variant")
        variants.add(case["variant"])
        require(case["jurisdiction"] == "us_il_urbana", "Unexpected case jurisdiction")
        require(bool(case["contract_text"].strip()) and bool(case["criterion"].strip()), "Missing input or criterion")
        require(bool(case["must_not_infer"]), "Missing negative criterion")
        validate_anchors(case["source_anchors"], sources)
    require(bool(pairs) and all(v == {"a", "b"} for v in pairs.values()), "Each contrast pair needs both variants")
    return {"draft_cases": len(ids), "contrast_pairs": len(pairs), "model_tested_cases": 0,
            "independently_adjudicated_cases": 0, "legal_accuracy": None, "risk_recall": None}


def read_pointer(document, pointer):
    require(isinstance(pointer, list) and bool(pointer), "Evidence pointer must be a nonempty list")
    value = document
    for part in pointer:
        require((isinstance(value, list) and type(part) is int and 0 <= part < len(value)) or
                (isinstance(value, dict) and isinstance(part, str) and part in value), "Invalid evidence pointer")
        value = value[part]
    return value


def validate_audit(data, root, sources):
    require(data["schema_version"] == 1 and data["review_status"] == "single_reviewer_source_check", "Unexpected audit schema/status")
    report_path = resolve_local(root, data["report_path"])
    # Universal newline reading keeps this text fingerprint stable across Git CRLF/LF checkouts.
    require(sha256(report_path.read_text(encoding="utf-8").encode()).hexdigest() == data["report_text_sha256"], "Reviewed report has changed")
    report = load_json(report_path)
    seen = set()
    verdicts = Counter()
    for finding in data["findings"]:
        require(finding["id"] not in seen, "Duplicate finding ID")
        seen.add(finding["id"])
        verdict = finding["verdict"]
        require(verdict in {"contradicted", "omitted", "supported_observation", "not_assessed"}, "Unknown verdict")
        require(bool(finding["rationale"].strip()), "Missing review rationale")
        require(bool(finding["evidence"]), "Missing report evidence")
        for evidence in finding["evidence"]:
            value = read_pointer(report, evidence["pointer"])
            require(isinstance(value, str) and bool(evidence["quote"].strip()) and evidence["quote"] in value,
                    "Quoted report evidence is absent")
        validate_anchors(finding["source_anchors"], sources)
        if "contract_evidence" in finding:
            contract = finding["contract_evidence"]
            text = resolve_local(root, contract["path"]).read_text(encoding="utf-8")
            require(sha256(text.encode()).hexdigest() == contract["text_sha256"], "Contract has changed")
            require(bool(contract["quote"].strip()) and contract["quote"] in text, "Contract quote missing")
        verdicts[verdict] += 1
    require(bool(seen), "Empty audit")
    return {"validated_review_records": len(seen), "record_verdicts": dict(verdicts),
            "independent_reviewers": 0, "legal_accuracy": None, "risk_recall": None,
            "note": "Evidence integrity only. Human judgments are not automatically established by matching quotes; findings are not an exhaustive denominator."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=HERE / "reasoning_cases.json")
    parser.add_argument("--audit", type=Path, default=HERE / "reasoning_audit_2026-10-29.json")
    args = parser.parse_args()
    root = HERE.parent.parent
    try:
        sources = load_sources(root)
        result = {"cases": validate_cases(load_json(args.cases), sources),
                  "existing_report_review": validate_audit(load_json(args.audit), root, sources),
                  "provider_requests": 0}
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(1, f"Review evidence validation failed: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

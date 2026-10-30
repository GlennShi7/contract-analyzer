"""Review evidence must not silently drift or fabricate completed evaluation."""
from copy import deepcopy
import json

import pytest

from eval.reasoning_review import (
    HERE, load_json, load_sources, resolve_local, validate_audit, validate_cases, validate_diagnostics,
)

ROOT = HERE.parent.parent


@pytest.fixture
def sources():
    return load_sources(ROOT)


@pytest.fixture
def cases():
    return load_json(HERE / "reasoning_cases.json")


@pytest.fixture
def audit():
    return load_json(HERE / "reasoning_audit_2026-10-29.json")


def test_draft_contrasts_are_not_reported_as_model_tests(cases, sources):
    result = validate_cases(cases, sources)
    assert result["draft_cases"] == 16 and result["contrast_pairs"] == 8
    assert result["model_tested_cases"] == 0
    assert result["independently_adjudicated_cases"] == 0
    assert result["legal_accuracy"] is None and result["risk_recall"] is None


def test_contrast_must_include_both_sides(cases, sources):
    cases["cases"].pop()
    with pytest.raises(ValueError, match="both variants"):
        validate_cases(cases, sources)


def test_duplicate_case_is_rejected(cases, sources):
    cases["cases"].append(deepcopy(cases["cases"][0]))
    with pytest.raises(ValueError, match="Duplicate case"):
        validate_cases(cases, sources)


def test_source_drift_requires_a_review_update(cases, sources):
    cases["cases"][0]["source_anchors"][0]["text_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="source has changed"):
        validate_cases(cases, sources)


def test_fabricated_statute_quote_is_rejected(cases, sources):
    cases["cases"][0]["source_anchors"][0]["quote"] = "Invented statutory requirement"
    with pytest.raises(ValueError, match="Source quote missing"):
        validate_cases(cases, sources)


def test_unperformed_runs_cannot_be_added_to_draft(cases, sources):
    cases["model_runs"] = [{"status": "passed"}]
    with pytest.raises(ValueError, match="unperformed model runs"):
        validate_cases(cases, sources)


def test_actual_review_records_have_evidence_but_no_accuracy_score(audit, sources):
    result = validate_audit(audit, ROOT, sources)
    assert result["validated_review_records"] == 7
    assert result["record_verdicts"] == {
        "contradicted": 1, "omitted": 2, "supported_observation": 3, "not_assessed": 1,
    }
    assert result["legal_accuracy"] is None and result["risk_recall"] is None


def test_reviewed_artifact_cannot_be_replaced(audit, sources):
    audit["report_text_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="report has changed"):
        validate_audit(audit, ROOT, sources)


def test_review_fingerprint_survives_crlf_checkout(audit, sources, tmp_path):
    for relative in (audit["report_path"], "backend/eval/contracts/lease_en.txt"):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        text = (ROOT / relative).read_text(encoding="utf-8")
        target.write_bytes(text.replace("\n", "\r\n").encode())
    assert validate_audit(audit, tmp_path, sources)["validated_review_records"] == 7


def test_fabricated_model_quote_is_rejected(audit, sources):
    audit["findings"][0]["evidence"][0]["quote"] = "Text the model did not generate"
    with pytest.raises(ValueError, match="report evidence is absent"):
        validate_audit(audit, ROOT, sources)


@pytest.mark.parametrize("pointer", [["rows", -1], ["rows", True], ["rows", 999], ["missing"]])
def test_wrong_evidence_location_is_rejected(audit, sources, pointer):
    audit["findings"][0]["evidence"][0]["pointer"] = pointer
    with pytest.raises(ValueError, match="Invalid evidence pointer"):
        validate_audit(audit, ROOT, sources)


def test_evidence_paths_stay_within_repository():
    with pytest.raises(ValueError, match="escapes repository"):
        resolve_local(ROOT, "../outside.json")


def test_tampered_source_text_is_rejected(tmp_path):
    path = tmp_path / "backend/laws/tenancy_us_il_urbana.json"
    path.parent.mkdir(parents=True)
    rows = load_json(ROOT / "backend/laws/tenancy_us_il_urbana.json")
    rows[0]["text"] += " Changed without updating the checksum."
    path.write_text(json.dumps(rows), encoding="utf-8")
    with pytest.raises(ValueError, match="Source checksum mismatch"):
        load_sources(tmp_path)


def test_actual_diagnostics_do_not_claim_the_blocked_case_was_rerun(cases, sources):
    data = load_json(HERE / "results/reasoning_20261029.json")
    result = validate_diagnostics(data, cases, sources)
    assert result["model_tested_cases"] == 4
    assert result["not_model_tested_cases"] == 12
    assert result["provider_requests_recorded"] == 8
    assert result["schema_accepted_generations"] == 7
    assert result["last_round_not_run"] == ["interest_fact_b"]
    assert result["legal_accuracy"] is None


def test_diagnostic_budget_and_input_drift_are_rejected(cases, sources):
    data = load_json(HERE / "results/reasoning_20261029.json")
    data["requests"].append(deepcopy(data["requests"][0]))
    with pytest.raises(ValueError, match="budget mismatch"):
        validate_diagnostics(data, cases, sources)
    data["requests"].pop()
    data["cases"][0]["contract_text"] += " An unauthorized extra condition."
    with pytest.raises(ValueError, match="differs from case manifest"):
        validate_diagnostics(data, cases, sources)


def test_billing_counter_blocks_ninth_sdk_call_and_saves_before_sending():
    from types import SimpleNamespace
    from eval.diagnostic_eval import CountedCompletions, BudgetExhausted

    ledger = {"requests": [], "current_case": "mock"}
    saved = []
    calls = []

    def create(**kwargs):
        assert len(saved) == len(calls) * 2 + 1
        calls.append(kwargs)
        return SimpleNamespace(model="mock", usage=None, choices=[])

    counted = CountedCompletions(SimpleNamespace(create=create), ledger, lambda: saved.append(len(ledger["requests"])))
    for _ in range(8):
        counted.create()
    with pytest.raises(BudgetExhausted):
        counted.create()
    assert len(calls) == len(ledger["requests"]) == 8


def test_failed_sdk_request_still_uses_allowance():
    from types import SimpleNamespace
    from eval.diagnostic_eval import CountedCompletions

    def fail(**kwargs):
        raise RuntimeError("mock network failure")

    ledger = {"requests": [], "current_case": "mock"}
    counted = CountedCompletions(SimpleNamespace(create=fail), ledger, lambda: None)
    with pytest.raises(RuntimeError, match="mock network"):
        counted.create()
    assert len(ledger["requests"]) == 1 and ledger["requests"][0]["status"] == "failed"


def test_diagnostic_prepare_mode_never_creates_client_or_ledger(monkeypatch, tmp_path):
    import sys
    import main as app
    from eval.diagnostic_eval import main

    def forbidden():
        raise AssertionError("Prepare mode must not create an API client")

    monkeypatch.setattr(app, "get_llm_client", forbidden)
    output = tmp_path / "unused.json"
    monkeypatch.setattr(sys, "argv", ["diagnostic_eval", "--output", str(output)])
    main()
    assert not output.exists()


def test_final_report_facts_have_contract_evidence_without_fake_law_ids(sources):
    data = load_json(HERE / "final_reasoning_audit_2026-10-29.json")
    result = validate_audit(data, ROOT, sources)
    assert result["validated_review_records"] == 5
    assert result["record_verdicts"] == {"contradicted": 3, "unsupported": 1, "omitted": 1}
    assert result["legal_accuracy"] is None and result["risk_recall"] is None


def test_contract_fact_finding_requires_contract_evidence(sources):
    data = load_json(HERE / "final_reasoning_audit_2026-10-29.json")
    del data["findings"][0]["contract_evidence"]
    with pytest.raises(ValueError, match="needs contract evidence"):
        validate_audit(data, ROOT, sources)


def test_profile_review_cannot_silently_change_jurisdiction(sources):
    data = load_json(HERE / "final_reasoning_audit_2026-10-29.json")
    data["findings"][-1]["profile_evidence"]["expected"] = "us_il_urbana"
    with pytest.raises(ValueError, match="profile differs"):
        validate_audit(data, ROOT, sources)

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from analyzer import AnalysisOutputError, analyze_contract, classify_contract
from eval import acceptance_eval as runner
from eval.acceptance_review import validate_findings, validate_ledger


def artifact():
    plan = runner.build_plan()
    item, spec = plan["inputs"][0], plan["rows"][0]
    requests = []
    output = {"contract_type": classify_contract(item["text"]), "risk_score": 1, "summary": "Synthetic offline test", "cards": []}
    raw = json.dumps(output)
    def complete(**kwargs):
        requests.append({"row_id": spec["id"], "status": "completed", "payload": deepcopy(kwargs),
                         "choices": [{"finish_reason": "stop", "content": raw}], "usage": None})
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=raw))])
    result = analyze_contract(item["text"], SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=complete))),
                              jurisdiction=item["jurisdiction"], model=plan["model"])
    return {"status": "partial_or_failed", "plan": plan, "requests": requests,
            "rows": [{**spec, "status": "validated", "result": result.model_dump(mode="json")}]}


def test_raw_response_replays_without_provider():
    summary = validate_ledger(artifact())
    assert summary["offline_provider_requests"] == 0 and summary["replayed_accepted_reports"] == 1
    assert summary["legal_accuracy"] is None and not summary["independent_adjudication"]


@pytest.mark.parametrize("change,match", [
    (lambda value: value["rows"][0]["result"].update(summary="tampered"), "Saved report"),
    (lambda value: value["requests"][0]["payload"].update(model="different"), "frozen production"),
    (lambda value: value.update(status="completed"), "missing/failed"),
    (lambda value: value["rows"].append(deepcopy(value["rows"][0])), "Duplicate generation"),
    (lambda value: value["requests"].extend([deepcopy(value["requests"][0])] * 76), "cap exceeded"),
])
def test_tampered_evidence_cannot_pass_replay(change, match):
    value = artifact()
    change(value)
    with pytest.raises(ValueError, match=match):
        validate_ledger(value)


def test_findings_require_exact_output_input_and_source_evidence():
    value = artifact()
    item = value["plan"]["inputs"][0]
    review = {"ledger_fingerprint": runner.digest(value), "independent_adjudication": False,
              "findings": [{"id": "f1", "verdict": "unknown", "rationale": "Test evidence anchor only",
                            "output_evidence": [{"pointer": ["rows", 0, "result", "summary"], "quote": "Synthetic offline test"}],
                            "input_evidence": [{"input_id": item["id"], "quote": item["text"]}],
                            "source_anchors": item["source_anchors"]}]}
    assert validate_findings(review, value)["evidence_anchored_findings"] == 1
    for target in ("output", "input", "source"):
        changed = deepcopy(review)
        key = {"output": "output_evidence", "input": "input_evidence", "source": "source_anchors"}[target]
        changed["findings"][0][key][0]["quote"] = "fabricated evidence"
        with pytest.raises(ValueError):
            validate_findings(changed, value)
    value["rows"][0]["result"]["summary"] = "changed after review"
    with pytest.raises(ValueError, match="ledger changed"):
        validate_findings(review, value)


def test_recorded_penalty_recipient_reversal_is_rejected_after_correction():
    saved = json.loads((Path(__file__).resolve().parents[1] / 'eval/results/completion_20261030/ledger.json').read_text(encoding='utf-8'))
    item = next(item for item in saved['plan']['inputs'] if item['id'] == 'labor_zh')
    records = [record for record in saved['requests'] if record['row_id'] == 'labor_zh:r1']
    calls = []
    def complete(**kwargs):
        record = records[len(calls)]
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason=c['finish_reason'], message=SimpleNamespace(content=c['content'])) for c in record['choices']])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=complete)))
    with pytest.raises(AnalysisOutputError):
        analyze_contract(item['text'], client, jurisdiction='cn')
    assert len(calls) == 2
    assert not any(message['role'] == 'assistant' for message in calls[1]['messages'])

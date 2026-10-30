from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from analyzer import AnalysisOutputError
from eval import acceptance_eval as runner


def response():
    return SimpleNamespace(model="stub", usage=None, choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content="{}"))])


def fixture(limit=2, count=2):
    return {"status": "prepared", "plan": {"fingerprint": "test", "model": "stub", "max_requests": limit,
            "inputs": [{"id": "synthetic", "text": "synthetic text", "jurisdiction": "unknown"}],
            "rows": [{"id": f"synthetic:r{i}", "input_id": "synthetic", "repeat": i} for i in range(count)]},
            "requests": [], "rows": []}


def client(create):
    return SimpleNamespace(max_retries=0, chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def analyze(text, counted, **kwargs):
    counted.chat.completions.create(messages=[{"role": "user", "content": text}], model=kwargs["model"])
    return SimpleNamespace(model_dump=lambda **kwargs: {"summary": "synthetic"})


def test_plan_has_all_existing_inputs_twice_and_conservative_budget():
    plan = runner.build_plan()
    assert len(plan["inputs"]) == 19 and len(plan["rows"]) == 38 and plan["max_requests"] == 76
    assert len({row["id"] for row in plan["rows"]}) == 38
    assert sum(case["kind"] == "diagnostic" for case in plan["inputs"]) == 16
    assert plan == runner.build_plan()
    assert all(case["jurisdiction"] == "cn" for case in plan["inputs"] if case["id"].endswith("_zh"))


def test_default_cli_prepares_without_creating_provider_client(tmp_path, monkeypatch, capsys):
    import main
    monkeypatch.setattr(main, "get_llm_client", lambda: pytest.fail("No client in prepare mode"))
    monkeypatch.setattr(sys, "argv", ["acceptance_eval", "--output", str(tmp_path)])
    runner.main()
    summary = json.loads(capsys.readouterr().out)
    assert summary["mode"] == "prepare_only" and summary["provider_requests_recorded"] == 0
    assert json.loads((tmp_path / "ledger.json").read_text(encoding="utf-8"))["requests"] == []
    review = json.loads((tmp_path / "review-template.json").read_text(encoding="utf-8"))
    assert review["legal_accuracy"] is None and review["independent_adjudication"] is False
    assert all(len(row["dimensions"]) == 7 for row in review["rows"])


def test_count_is_durable_before_provider_and_resume_never_resets(tmp_path):
    ledger = fixture(limit=1)
    path = tmp_path / "ledger.json"
    def create(**kwargs):
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert len(saved["requests"]) == 1 and saved["requests"][0]["status"] == "started"
        return response()
    persist = lambda: runner.save(path, ledger)
    runner.run_batch(ledger, client(create), persist, analyze)
    assert ledger["status"] == "partial_or_failed" and len(ledger["requests"]) == 1
    resumed = json.loads(path.read_text(encoding="utf-8"))
    runner.run_batch(resumed, client(lambda **kwargs: pytest.fail("Cumulative budget exhausted")), lambda: None, analyze)
    assert len(resumed["requests"]) == 1 and len(resumed["rows"]) == 1


def test_correction_and_provider_failures_both_count():
    ledger = fixture(limit=2, count=1)
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        if len(calls) == 2:
            raise RuntimeError("simulated connection failure")
        return response()
    def correct(text, counted, **kwargs):
        for _ in range(2):
            counted.chat.completions.create(model="stub", messages=[])
    with pytest.raises(RuntimeError):
        runner.run_batch(ledger, client(create), lambda: None, correct)
    assert len(ledger["requests"]) == 2
    assert [r["status"] for r in ledger["requests"]] == ["completed", "failed"]
    assert ledger["status"] == "partial_or_failed" and ledger["rows"][0]["status"] == "failed"


def test_sdk_retry_configuration_rejected_before_any_send():
    raw = client(lambda **kwargs: pytest.fail("No call"))
    raw.max_retries = 2
    with pytest.raises(ValueError, match="retries"):
        runner.run_batch(fixture(), raw, lambda: None, analyze)


def test_exclusive_lock_prevents_simultaneous_or_stale_run(tmp_path):
    with runner.exclusive(tmp_path):
        with pytest.raises(FileExistsError):
            with runner.exclusive(tmp_path):
                pytest.fail("Two owners")
    assert not (tmp_path / "active.lock").exists()
    (tmp_path / "active.lock").write_text("abandoned", encoding="utf-8")
    with pytest.raises(FileExistsError):
        with runner.exclusive(tmp_path):
            pytest.fail("Stale lock was bypassed")


def test_interrupted_row_is_retained_without_regeneration():
    ledger = fixture()
    ledger["rows"] = [ledger["plan"]["rows"][0] | {"status": "pending"}]
    ledger["requests"] = [{"row_id": ledger["rows"][0]["id"], "status": "started"}]
    runner.run_batch(ledger, client(lambda **kwargs: response()), lambda: None, analyze)
    assert ledger["rows"][0]["status"] == "interrupted"
    assert len(ledger["requests"]) == 2 and ledger["requests"][1]["row_id"].endswith("r1")
    assert ledger["status"] == "partial_or_failed"


def test_failed_validation_does_not_erase_requests_or_skip_other_rows():
    ledger = fixture(limit=4)
    def reject(text, counted, **kwargs):
        counted.chat.completions.create(model="stub", messages=[])
        counted.chat.completions.create(model="stub", messages=[])
        raise AnalysisOutputError("invalid")
    runner.run_batch(ledger, client(lambda **kwargs: response()), lambda: None, reject)
    assert len(ledger["requests"]) == 4 and all(row["status"] == "failed" for row in ledger["rows"])
    assert ledger["status"] == "partial_or_failed"


def test_resume_rejects_changed_plan_before_client(tmp_path, monkeypatch):
    import main
    plan = runner.build_plan()
    ledger = {"plan": deepcopy(plan), "requests": [], "rows": [], "status": "prepared"}
    ledger["plan"]["model"] = "different"
    runner.save(tmp_path / "plan.json", plan)
    runner.save(tmp_path / "ledger.json", ledger)
    monkeypatch.setattr(main, "get_llm_client", lambda: pytest.fail("Changed plan reached provider"))
    monkeypatch.setattr(sys, "argv", ["acceptance_eval", "--output", str(tmp_path), "--resume", "--live"])
    with pytest.raises(SystemExit) as error:
        runner.main()
    assert error.value.code == 2


def test_existing_ledger_cannot_be_overwritten_without_resume(tmp_path, monkeypatch):
    (tmp_path / "ledger.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["acceptance_eval", "--output", str(tmp_path)])
    with pytest.raises(SystemExit) as error:
        runner.main()
    assert error.value.code == 2
    assert (tmp_path / "ledger.json").read_text(encoding="utf-8") == "{}"


def test_worksheet_does_not_call_missing_or_validated_output_a_pass():
    ledger = fixture()
    ledger["rows"] = [ledger["plan"]["rows"][0] | {"status": "validated"}]
    review = runner.worksheet(ledger)
    assert [r["generation_status"] for r in review["rows"]] == ["validated", "not_run"]
    assert all(d["verdict"] == "unreviewed" for row in review["rows"] for d in row["dimensions"].values())

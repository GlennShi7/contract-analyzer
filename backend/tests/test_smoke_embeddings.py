"""The test inspector must not share a live PersistentClient directory."""
import json
from pathlib import Path
import runpy
import subprocess
from types import SimpleNamespace

import pytest


@pytest.fixture
def inspector():
    return runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/smoke_embeddings.py"))["inspect"]


def result(code=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=code, stdout=stdout, stderr=stderr)


def test_exclusive_inspector_stops_app_before_opening_volumes_and_restores_it(inspector, monkeypatch):
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        if argv[2] == "run":
            assert calls[0][2] == "stop"
            assert "--rm" in argv and "--no-deps" in argv
            assert "HF_HUB_OFFLINE=1" in argv and "exec" not in argv
            assert json.loads(kwargs["input"])["question"] == "test question"
            return result(stdout='SMOKE_RESULT={"offline_inspection":true,"rows":[]}\n')
        return result()

    monkeypatch.setitem(inspector.__globals__, "subprocess", SimpleNamespace(run=run))
    assert inspector([], "test question", "span", exclusive=True)["offline_inspection"] is True
    assert [call[2] for call in calls] == ["stop", "run", "up"]
    assert "--wait" in calls[-1] and calls[-1][-1] == "backend"


def test_failed_inspection_keeps_partial_output_and_restores_backend(inspector, monkeypatch):
    calls = []

    def run(argv, **kwargs):
        calls.append(argv[2])
        return result(1, "SMOKE_OBSERVATION=partial diagnostics", "missing answer") if argv[2] == "run" else result()

    monkeypatch.setitem(inspector.__globals__, "subprocess", SimpleNamespace(run=run))
    with pytest.raises(SystemExit) as error:
        inspector([], "test", "span", exclusive=True)
    assert "partial diagnostics" in str(error.value) and "missing answer" in str(error.value)
    assert calls == ["stop", "run", "up"]


def test_inspection_timeout_still_attempts_backend_restore(inspector, monkeypatch):
    calls = []

    def run(argv, **kwargs):
        calls.append(argv[2])
        if argv[2] == "run":
            raise subprocess.TimeoutExpired(argv, 180)
        return result()

    monkeypatch.setitem(inspector.__globals__, "subprocess", SimpleNamespace(run=run))
    with pytest.raises(subprocess.TimeoutExpired):
        inspector([], "test", "span", exclusive=True)
    assert calls == ["stop", "run", "up"]


def test_stop_failure_never_opens_another_client_and_attempts_restore(inspector, monkeypatch):
    calls = []

    def run(argv, **kwargs):
        calls.append(argv[2])
        return result(1, stderr="cannot stop") if argv[2] == "stop" else result()

    monkeypatch.setitem(inspector.__globals__, "subprocess", SimpleNamespace(run=run))
    with pytest.raises(SystemExit, match="exclusive"):
        inspector([], "test", "span", exclusive=True)
    assert calls == ["stop", "up"]


def test_missing_exclusive_flag_cannot_stop_or_query_a_stack(inspector, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No container command is permitted without explicit exclusive mode")

    monkeypatch.setitem(inspector.__globals__, "subprocess", SimpleNamespace(run=forbidden))
    with pytest.raises(ValueError, match="exclusive"):
        inspector([], "test", "span")

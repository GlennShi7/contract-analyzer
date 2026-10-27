import hashlib
from pathlib import Path

import pytest


def test_same_bytes_have_same_id_and_same_filename_does_not_merge_documents(api, pdf_factory, collection):
    client, _ = api
    first_pdf = pdf_factory("Deposit returned in 10 days.")
    second_pdf = pdf_factory("Deposit returned in 90 days.")
    first = client.post("/upload", files={"file": ("lease.pdf", first_pdf, "application/pdf")})
    renamed = client.post("/upload", files={"file": ("renamed.pdf", first_pdf, "application/pdf")})
    second = client.post("/upload", files={"file": ("lease.pdf", second_pdf, "application/pdf")})
    assert first.status_code == renamed.status_code == second.status_code == 200
    assert first.json()["doc_id"] == hashlib.sha256(first_pdf).hexdigest() == renamed.json()["doc_id"]
    assert first.json()["doc_id"] != second.json()["doc_id"]
    assert first.json()["n_chunks"] == 1
    assert "text" not in first.json()
    assert collection.count() == 2


def test_analyze_loads_the_selected_document_and_ask_returns_only_its_sources(api, pdf_factory):
    client, calls = api
    first = client.post("/upload", files={"file": ("lease.pdf", pdf_factory("Deposit returned in 10 days."))}).json()
    second = client.post("/upload", files={"file": ("lease.pdf", pdf_factory("Deposit returned in 90 days."))}).json()
    analysis = client.post("/analyze", json={"doc_id": first["doc_id"]})
    assert analysis.status_code == 200
    assert isinstance(analysis.json()["result"], dict)
    assert analysis.json()["result"]["grounding"]["cards_total"] == 0
    assert "10 days" in calls[-1]["messages"][-1]["content"]
    assert "90 days" not in calls[-1]["messages"][-1]["content"]
    answer = client.post("/ask", json={"doc_id": second["doc_id"], "question": "When is my deposit returned?"})
    assert answer.status_code == 200
    assert {source["doc_id"] for source in answer.json()["sources"]} == {second["doc_id"]}
    assert "90 days" in calls[-1]["messages"][-1]["content"]
    assert "10 days" not in calls[-1]["messages"][-1]["content"]


def test_ask_uses_three_chunks(api, monkeypatch):
    import main
    client, _ = api
    observed = []
    monkeypatch.setattr(main, "contract_text", lambda doc_id: "contract")

    def search(query, doc_id, n_results):
        observed.append(n_results)
        return [{"text": "clause", "doc_id": doc_id, "chunk": 0}]

    monkeypatch.setattr(main, "search_chunks", search)
    assert client.post("/ask", json={"doc_id": "a" * 64, "question": "deposit?"}).status_code == 200
    assert observed == [3]


@pytest.mark.parametrize("endpoint,payload", [
    ("/analyze", {"doc_id": "a" * 64}),
    ("/ask", {"doc_id": "a" * 64, "question": "deposit?"}),
])
def test_unknown_document_is_404_without_llm_call(api, endpoint, payload):
    client, calls = api
    assert client.post(endpoint, json=payload).status_code == 404
    assert not calls


def test_invalid_ids_and_blank_questions_are_rejected(api):
    client, calls = api
    assert client.post("/analyze", json={"doc_id": "../private"}).status_code == 422
    assert client.post("/ask", json={"doc_id": "a" * 64, "question": "   "}).status_code == 422
    assert not calls


@pytest.mark.parametrize("kind", ["invalid", "blank", "valid"])
def test_upload_uses_safe_temporary_path_and_cleans_it(api, pdf_factory, monkeypatch, kind):
    import main
    client, _ = api
    observed = []
    original = main.extract_text

    def parse(path):
        observed.append(Path(path))
        return original(path)

    monkeypatch.setattr(main, "extract_text", parse)
    content = b"not a PDF" if kind == "invalid" else pdf_factory("" if kind == "blank" else "Lease text.")
    result = client.post("/upload", files={"file": ("../../outside.pdf", content, "application/pdf")})
    assert result.status_code == (200 if kind == "valid" else 400)
    assert len(observed) == 1
    assert observed[0].name != "outside.pdf"
    assert not observed[0].exists()


def test_missing_index_is_409_without_llm_call(api, monkeypatch):
    import main
    client, calls = api
    monkeypatch.setattr(main, "contract_text", lambda doc_id: "contract")
    response = client.post("/ask", json={"doc_id": "a" * 64, "question": "deposit?"})
    assert response.status_code == 409
    assert not calls


@pytest.mark.parametrize("endpoint", ["/analyze", "/ask"])
def test_generation_failure_returns_502(api, monkeypatch, endpoint):
    import httpx
    import main
    from openai import APIConnectionError
    client, _ = api
    monkeypatch.setattr(main, "contract_text", lambda doc_id: "Contract text.")
    monkeypatch.setattr(main, "search_chunks", lambda *args, **kwargs: [{"text": "clause", "doc_id": "a" * 64, "chunk": 0}])

    def fail(**kwargs):
        raise APIConnectionError(request=httpx.Request("POST", "https://api.deepseek.com"))

    monkeypatch.setattr(main.get_llm_client().chat.completions, "create", fail)
    response = client.post(endpoint, json={"doc_id": "a" * 64, "question": "deposit?"})
    assert response.status_code == 502
    assert isinstance(response.json()["detail"], str)


def test_missing_api_key_does_not_crash_import_and_is_503(monkeypatch):
    import main
    from fastapi import HTTPException
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    main.get_llm_client.cache_clear()
    with pytest.raises(HTTPException) as error:
        main.get_llm_client()
    assert error.value.status_code == 503


def test_analysis_jurisdiction_controls_statute_injection(api, monkeypatch):
    import main
    client, calls = api
    monkeypatch.setattr(main, "contract_text", lambda doc_id: "出租人与承租人约定押金。")
    unknown = client.post("/analyze", json={"doc_id": "a" * 64})
    assert unknown.status_code == 200
    assert "住房租赁条例-10" not in calls[-1]["messages"][0]["content"]
    mainland = client.post("/analyze", json={"doc_id": "a" * 64, "jurisdiction": "cn"})
    assert mainland.status_code == 200
    assert "住房租赁条例-10" in calls[-1]["messages"][0]["content"]
    assert "中国大陆" in mainland.json()["result"]["legal_scope"]
    assert client.post("/analyze", json={"doc_id": "a" * 64, "jurisdiction": "us"}).status_code == 422


def test_invalid_structured_analysis_returns_502_after_one_retry(api, monkeypatch):
    from types import SimpleNamespace
    import main
    client, _ = api
    monkeypatch.setattr(main, "contract_text", lambda doc_id: "合同文字")
    calls = []

    def invalid(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content="bad"))])

    monkeypatch.setattr(main.get_llm_client().chat.completions, "create", invalid)
    response = client.post("/analyze", json={"doc_id": "a" * 64})
    assert response.status_code == 502
    assert "格式校验" in response.json()["detail"]
    assert len(calls) == 2

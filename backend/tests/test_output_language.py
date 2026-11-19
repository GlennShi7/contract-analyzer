import json
from types import SimpleNamespace

import pytest

from analyzer import AnalysisOutputError, analyze_contract

LEASE = "Residential lease. Landlord and tenant agree. Monthly rent is $500. Tenant forfeits the security deposit if late."
QUOTE = "Tenant forfeits the security deposit if late."


def output(summary, title, explanation, suggestion):
    return json.dumps({"contract_type": "lease", "risk_score": 6, "summary": summary, "cards": [
        {"title": title, "category": "risk", "checklist_item": 1, "clause_text": QUOTE, "risk_level": "high", "explanation": explanation,
         "legal_basis": [], "suggestion": suggestion}]})


ZH = output("押金条款对租客不利，需要核实。", "迟交即没收押金", "这条把迟交房租和没收全部押金挂钩。", "签约前要求删除或改为按实际损失扣除。")
EN = output("The deposit clause is one-sided and should be checked.", "Deposit forfeited for late rent",
            "Any late payment lets the landlord keep the whole deposit.", "Ask to replace it with deductions for actual losses.")


def stub(*contents):
    calls, replies = [], iter(contents)

    def create(**kwargs):
        calls.append(kwargs | {"messages": [dict(m) for m in kwargs["messages"]]})
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=next(replies)))])

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))), calls


@pytest.mark.parametrize("language, reply, marker, example", [
    ("en", EN, "Write summary, title, explanation and suggestion in English", "Verbatim text copied from the contract"),
    ("zh", ZH, "用简体中文书写", "从合同中逐字复制的原文"),
])
def test_prompt_and_example_follow_the_chosen_language(language, reply, marker, example):
    client, calls = stub(reply)
    result = analyze_contract(LEASE, client, output_language=language)
    system = calls[0]["messages"][0]["content"]
    assert marker in system and example in system and "输出中文" not in system
    assert result.cards[0].clause_text == QUOTE and result.attempts == 1


def test_chinese_reader_of_an_english_lease_gets_chinese_prose_and_english_quotes():
    client, _ = stub(ZH)
    result = analyze_contract(LEASE, client, output_language="zh")
    assert result.summary.startswith("押金") and result.cards[0].clause_text == QUOTE


def test_wrong_language_is_corrected_once_from_the_original_input():
    client, calls = stub(ZH, EN)
    result = analyze_contract(LEASE, client, output_language="en")
    assert result.summary.startswith("The deposit") and result.attempts == 2
    correction = calls[1]["messages"][-1]["content"]
    assert "English" in correction and len(calls[1]["messages"]) == 3


def test_wrong_language_twice_is_rejected():
    client, calls = stub(EN, EN)
    with pytest.raises(AnalysisOutputError):
        analyze_contract(LEASE, client, output_language="zh")
    assert len(calls) == 2


def test_chinese_prose_may_name_english_statutes():
    mixed = output("押金条款可能违反 Urbana 12.5-20 和 765 ILCS 710/1 的规定。", "押金扣除", "Urbana Code 12.5-20 要求逐项清单。", "保留 move-in checklist 照片。")
    client, _ = stub(mixed)
    assert analyze_contract(LEASE, client, output_language="zh").attempts == 1


def test_api_passes_the_language_and_rejects_unknown_values(api, pdf_factory):
    client, calls = api
    doc = client.post("/upload", files={"file": ("lease.pdf", pdf_factory(LEASE))}).json()["doc_id"]
    assert client.post("/analyze", json={"doc_id": doc, "output_language": "en"}).status_code == 200
    assert "in English" in calls[-1]["messages"][0]["content"]
    assert client.post("/analyze", json={"doc_id": doc}).status_code == 200
    assert "用简体中文书写" in calls[-1]["messages"][0]["content"]  # API default keeps earlier behavior
    assert client.post("/analyze", json={"doc_id": doc, "output_language": "fr"}).status_code == 422


@pytest.mark.parametrize("question, language, expected", [
    ("When is the deposit returned?", None, "Answer in English"),
    ("押金什么时候退？", None, "用简体中文回答"),
    ("When is the deposit returned?", "zh", "用简体中文回答"),
    ("押金什么时候退？", "en", "Answer in English"),
])
def test_questions_are_answered_in_the_chosen_or_asked_language(api, pdf_factory, question, language, expected):
    client, calls = api
    doc = client.post("/upload", files={"file": ("lease.pdf", pdf_factory(LEASE))}).json()["doc_id"]
    body = {"doc_id": doc, "question": question} | ({"output_language": language} if language else {})
    assert client.post("/ask", json=body).status_code == 200
    assert expected in calls[-1]["messages"][0]["content"]

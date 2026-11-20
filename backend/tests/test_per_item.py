"""Per-item review: one call per checklist item, verdicts, template missing cards, merging and failure isolation.

The stub model answers per item from a table; synthetic lease text only.
"""
import json
import threading
from types import SimpleNamespace

import pytest

import per_item
from analyzer import load_checklist
from per_item import analyze_contract_per_item, risk_score

DEPOSIT = "1.4 SECURITY DEPOSIT\nThe security deposit will be forfeited and applied to cleaning charges and attorney's fees incurred by Lessor."
LATE = "1.3 RENT\nRent is due on the first. A late fee of 5% of the entire outstanding balance is charged after five days."
SUBLET = "4.1 SUBLETTING\nThe lessee agrees not to sublet the premises or any portion thereof without the lessor's prior approval."
HOLD = "3.5 MOVE-OUT\nLessee shall pay $200 per day for each day Lessee stays in possession after the term ends as a holdover."
PAGES = ["Residential lease for a unit in Urbana, Illinois. Landlord and tenant agree as follows.\n" + DEPOSIT + "\n" + LATE, SUBLET + "\n" + HOLD]
TEXT = "\n\n".join(PAGES)


def card(segment, quote, category="risk", title="Problem", basis=(), level="medium", language="en"):
    words = ("A short explanation.", "Ask the landlord.") if language == "en" else ("简短解释。", "问房东。")
    return {"segment": segment, "title": title, "category": category, "clause_text": quote, "risk_level": level,
            "explanation": words[0], "legal_basis": list(basis), "suggestion": words[1]}


def stub(answers, *, summary="Summary of the findings.", default=None):
    """answers: item id -> list of replies (dicts, raw strings, exceptions, or callables taking the payload)."""
    calls, lock = [], threading.Lock()
    queues = {item: list(replies) for item, replies in answers.items()}

    def create(**kwargs):
        user = kwargs["messages"][1]["content"]
        payload = json.loads(user)
        with lock:
            calls.append(kwargs | {"messages": [dict(m) for m in kwargs["messages"]]})
        if "segments" not in payload:
            content, finish = (summary if isinstance(summary, str) and summary.startswith("{") else json.dumps({"summary": summary})), "stop"
        else:
            item = payload["item"]["id"]
            with lock:
                queue = queues.get(item)
                reply = queue.pop(0) if queue else (default(payload) if default else {"verdict": "no_problem", "cards": []})
            if isinstance(reply, Exception):
                raise reply
            if callable(reply):
                reply = reply(payload)
            finish = "stop"
            if isinstance(reply, tuple):
                reply, finish = reply
            content = reply if isinstance(reply, str) else json.dumps(reply, ensure_ascii=False)
        return SimpleNamespace(usage=SimpleNamespace(prompt_tokens=100, completion_tokens=10),
                               choices=[SimpleNamespace(finish_reason=finish, message=SimpleNamespace(content=content))])

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))), calls


def segment_with(payload, text):
    return next(s["id"] for s in payload["segments"] if text in s["text"])


def problem(quote, **kwargs):
    return lambda payload: {"verdict": "problem", "cards": [card(segment_with(payload, quote), quote, **kwargs)], "note": "test"}


def run(answers, **kwargs):
    client, calls = stub(answers, **{k: kwargs.pop(k) for k in ("summary", "default") if k in kwargs})
    result = analyze_contract_per_item(TEXT, client, pages=PAGES, jurisdiction="us_il_urbana", output_language="en", **kwargs)
    return result, calls


def item_calls(calls):
    return [c for c in calls if "segments" in json.loads(c["messages"][1]["content"])]


def test_each_item_with_candidates_gets_one_call_with_only_its_segments_and_laws():
    late = "A late fee of 5% of the entire outstanding balance is charged after five days."
    result, calls = run({4: [problem(late, category="conflict", basis=["URBANA-12.5-13"], level="high")]})
    judged = item_calls(calls)
    assert result.grounding.pipeline == "per_item" and len(judged) == result.grounding.calls - 1
    payload = json.loads(next(c for c in judged if json.loads(c["messages"][1]["content"])["item"]["id"] == 4)["messages"][1]["content"])
    assert {law["id"] for law in payload["laws"]} <= set(load_checklist()[4]["laws"]) and payload["laws"]
    assert len(payload["segments"]) <= 8 and all({"id", "pages", "text"} <= set(s) for s in payload["segments"])
    assert {c["messages"][0]["content"] for c in judged} == {judged[0]["messages"][0]["content"]}  # shared prefix
    late_card = next(c for c in result.cards if c.checklist_item == 4)
    assert late_card.category == "conflict" and late_card.legal_basis == ["URBANA-12.5-13"] and late_card.pages == [1]
    assert all(c["max_tokens"] == per_item.ITEM_MAX_TOKENS and c["temperature"] == 0 for c in judged)


def test_no_problem_means_no_cards_and_unclear_means_verify():
    sublet = "The lessee agrees not to sublet the premises or any portion thereof without the lessor's prior approval."
    deposit = "The security deposit will be forfeited and applied to cleaning charges and attorney's fees incurred by Lessor."
    result, _ = run({
        19: [lambda p: {"verdict": "no_problem", "cards": [card(segment_with(p, sublet), sublet)]}],
        1: [lambda p: {"verdict": "unclear", "cards": [card(segment_with(p, deposit), deposit, category="conflict", basis=["URBANA-12.5-20"])]}],
    })
    assert not any(c.checklist_item == 19 for c in result.cards)
    assert next(c for c in result.cards if c.checklist_item == 1).category == "verify"
    assert result.grounding.item_verdicts[19] == "no_problem" and result.grounding.item_verdicts[1] == "unclear"


def test_a_quote_not_in_the_segments_is_retried_with_the_reason_then_the_item_is_marked_unchecked():
    bad = lambda p: {"verdict": "problem", "cards": [card(p["segments"][0]["id"], "Tenant waives all rights forever.")]}
    result, calls = run({23: [bad, bad]})
    retries = [c for c in item_calls(calls) if json.loads(c["messages"][1]["content"])["item"]["id"] == 23]
    assert len(retries) == 2 and "找不到" in retries[1]["messages"][-1]["content"]
    assert result.grounding.items_failed == [23] and result.grounding.item_verdicts[23] == "failed"
    assert any(reason.startswith("第 23 项") for reason in result.grounding.retry_reasons)


def test_a_failed_item_does_not_sink_the_others():
    sublet = "The lessee agrees not to sublet the premises or any portion thereof without the lessor's prior approval."
    result, _ = run({23: [RuntimeError("boom"), RuntimeError("boom")], 19: [problem(sublet)]})
    assert result.grounding.items_failed == [23]
    assert any(c.checklist_item == 19 for c in result.cards)


def test_a_cut_off_or_wrong_language_reply_is_retried():
    hold = "Lessee shall pay $200 per day for each day Lessee stays in possession after the term ends as a holdover."
    result, calls = run({23: [('{"verdict": "problem", "cards": [', "length"), problem(hold, language="zh"), problem(hold)]})
    assert result.grounding.items_failed == [23]  # two attempts only
    result, _ = run({23: [problem(hold, language="zh"), problem(hold)]})
    assert any(c.checklist_item == 23 for c in result.cards)


def test_items_the_lease_lacks_get_a_template_card_without_a_call():
    result, calls = run({})
    called = {json.loads(c["messages"][1]["content"])["item"]["id"] for c in item_calls(calls)}
    missing = [c for c in result.cards if c.category == "missing"]
    assert missing and all(c.checklist_item not in called for c in missing)
    assert set(result.grounding.items_missing) == {c.checklist_item for c in missing}
    lead = next((c for c in missing if c.checklist_item == 24), None)
    assert lead is not None and "1978" in lead.explanation  # the template states when the rule applies


def test_the_same_clause_under_two_items_is_kept_once_under_the_stronger_card():
    deposit = "The security deposit will be forfeited and applied to cleaning charges and attorney's fees incurred by Lessor."
    result, _ = run({1: [problem(deposit, level="medium")],
                     16: [problem(deposit, category="conflict", basis=["URBANA-12.5-10"], level="high")]})
    same = [c for c in result.cards if c.clause_text.startswith("The security deposit will be forfeited")]
    assert len(same) == 1 and same[0].checklist_item == 16 and same[0].also_items == [1]
    assert result.grounding.duplicates_merged == 1


def test_summary_comes_from_cards_and_falls_back_when_the_call_fails():
    late = "A late fee of 5% of the entire outstanding balance is charged after five days."
    result, calls = run({4: [problem(late)]}, summary="One late-fee issue.")
    summary_call = next(c for c in calls if "segments" not in json.loads(c["messages"][1]["content"]))
    assert "cards" in json.loads(summary_call["messages"][1]["content"]) and TEXT not in summary_call["messages"][1]["content"]
    assert result.summary == "One late-fee issue."
    result, _ = run({4: [problem(late)]}, summary="{not json")
    assert result.summary.startswith("The per-item review raised")


def test_risk_score_is_a_fixed_formula():
    c = lambda category, level="medium": SimpleNamespace(category=category, risk_level=level)
    assert risk_score([]) == 1
    assert risk_score([c("risk", "low")]) == 1
    assert risk_score([c("conflict")] * 3) == round(2 * __import__("math").log2(10))
    assert risk_score([c("conflict")] * 50) == 10


def test_contracts_without_a_checklist_keep_the_single_call(monkeypatch):
    called = {}
    monkeypatch.setattr(per_item, "analyze_contract", lambda *a, **k: called.setdefault("single", True) or "single")
    client, _ = stub({})
    assert analyze_contract_per_item("出租人和承租人约定：押金一千元。", client, jurisdiction="cn") is True


def test_report_language_follows_the_request():
    client, calls = stub({}, default=lambda p: {"verdict": "no_problem", "cards": []})
    analyze_contract_per_item(TEXT, client, pages=PAGES, jurisdiction="us_il_urbana", output_language="zh")
    system = item_calls(calls)[0]["messages"][0]["content"]
    assert "简体中文" in system and "不下法律结论" in system and "category 只能是 conflict、risk、verify" in system


@pytest.fixture
def lease_pdf(pdf_factory):
    return pdf_factory(PAGES)


def test_analyze_endpoint_runs_the_per_item_pipeline(api, lease_pdf, monkeypatch):
    import main
    client, _ = api
    doc_id = client.post("/upload", files={"file": ("lease.pdf", lease_pdf, "application/pdf")}).json()["doc_id"]
    seen = {}

    def fake(text, llm, *, pages, jurisdiction, output_language):
        seen.update(pages=pages, jurisdiction=jurisdiction)
        return main.analyze_contract(text, llm, jurisdiction=jurisdiction, output_language=output_language)

    monkeypatch.setattr(main, "analyze_contract_per_item", fake)
    response = client.post("/analyze", json={"doc_id": doc_id, "jurisdiction": "us_il_urbana", "pipeline": "per_item"})
    assert response.status_code == 200 and seen["jurisdiction"] == "us_il_urbana" and len(seen["pages"]) == 2


def test_long_contracts_must_use_the_per_item_pipeline(api, monkeypatch):
    import main
    client, calls = api
    monkeypatch.setattr(main, "contract_text", lambda doc_id: "x" * (main.SINGLE_CALL_MAX_CHARS + 1))
    response = client.post("/analyze", json={"doc_id": "a" * 64})
    assert response.status_code == 413 and "逐项检查" in response.json()["detail"] and not calls


def test_scoring_explains_why_an_item_was_missed():
    from eval import score_eval
    record = {"result": {"cards": [], "grounding": {"item_verdicts": {"4": "no_problem", "23": "failed"}}}}
    s = score_eval.score_run(record, {4: "风险", 23: "违法/无效", 1: "没问题"}, load_checklist(), None, "r")
    assert s["miss_verdicts"] == {4: "no_problem", 23: "failed"}


def test_a_merged_card_counts_for_every_item_it_lists():
    from eval import score_eval
    record = {"result": {"cards": [{"checklist_item": 22, "also_items": [41], "category": "risk", "legal_basis": []}]}}
    s = score_eval.score_run(record, {22: "风险", 41: "风险"}, load_checklist(), None, "r")
    assert s["hits"] == [22, 41]


def test_curly_quotes_in_the_lease_match_straight_quotes_in_the_model_copy():
    from analyzer import match_quote
    lease = "Landlord may enter the Bedroom without notice to Resident and without Resident’s consent – at any time."
    assert match_quote("without Resident's consent - at any time.", lease)[0] == "whitespace"
    curly = "1.4 ENTRY\nLandlord may enter the Bedroom without notice to Resident and without Resident’s consent at any time."
    client, _ = stub({18: [lambda p: {"verdict": "problem", "cards": [card(segment_with(p, "without notice"),
                     "Landlord may enter the Bedroom without notice to Resident and without Resident's consent at any time.")]}]})
    result = analyze_contract_per_item(curly + "\n\n" + TEXT, client, pages=[curly] + PAGES, jurisdiction="us_il_urbana", output_language="en")
    assert 18 not in result.grounding.items_failed and any(c.checklist_item == 18 and c.verified for c in result.cards)


def test_english_reports_state_the_urbana_premise_in_english():
    late = "A late fee of 5% of the entire outstanding balance is charged after five days."

    def reply(payload):
        c = card(segment_with(payload, late), late, category="conflict", basis=["URBANA-12.5-13"])
        c["explanation"] = ("The clause charges five percent of the entire outstanding balance, while the ordinance limits "
                            "late fees to a share of the monthly rent. 前提：房产在 Urbana 市界内")
        return {"verdict": "problem", "cards": [c]}

    result, _ = run({4: [reply]})
    late_card = next(c for c in result.cards if c.checklist_item == 4)
    assert "前提" not in late_card.explanation and late_card.explanation.endswith("Assumes the property is inside Urbana city limits.")

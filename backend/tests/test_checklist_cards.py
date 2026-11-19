import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import analyzer
from analyzer import AnalysisOutputError, AnalysisResult, CHECKLIST_SIZE, analyze_contract, load_checklist

REPO = Path(__file__).resolve().parents[2]
LEASE = ("Residential lease. Landlord and tenant agree. Monthly rent is $500. Security deposit is $500. "
         "Tenant forfeits the security deposit if late. A holdover fee of $200 per day applies. "
         "Carpets must be professionally shampooed at Tenant's expense. Tenant shall pay a $10 monthly portal fee.")


def card(item, category="risk", quote="Tenant forfeits the security deposit if late.", level="high", basis=(), title="押金条款"):
    return {"title": title, "category": category, "checklist_item": item, "clause_text": quote, "risk_level": level,
            "explanation": "这条对租客不利。", "legal_basis": list(basis), "suggestion": "签约前核实。"}


def stub(*outputs):
    calls, replies = [], iter(outputs)

    def create(**kwargs):
        calls.append(kwargs | {"messages": [dict(m) for m in kwargs["messages"]]})
        content = json.dumps({"contract_type": "lease", "risk_score": 7, "summary": "这份租约有多处需要核实。", "cards": next(replies)})
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=content))])

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))), calls


def test_checklist_file_matches_the_card_schema():
    items = load_checklist()
    assert sorted(items) == list(range(1, CHECKLIST_SIZE + 1))
    assert {i["tier"] for i in items.values()} == {"universal", "common", "rare"}
    assert all(i["keywords"] and i["name_en"] and i["description_zh"] for i in items.values())


def test_lease_prompt_walks_the_checklist_but_labor_and_mainland_leases_do_not():
    client, calls = stub([])
    analyze_contract(LEASE, client, jurisdiction="us_il_urbana")
    system = calls[0]["messages"][0]["content"]
    assert f"逐项检查以下 {CHECKLIST_SIZE} 项清单" in system and "18. 房东入户" in system and "missing" in system
    client, calls = stub([])
    analyze_contract("出租人和承租人约定：租金每月一千元，押金一千元。", client, jurisdiction="cn")
    assert "逐项检查以下" not in calls[0]["messages"][0]["content"]


def test_more_than_twelve_problems_are_kept():
    quotes = [s + "." for s in LEASE.split(". ") if s] * 4
    cards = [card((i % CHECKLIST_SIZE) + 1, quote=q.rstrip(".") + ".") for i, q in enumerate(quotes[:27])]
    client, calls = stub(cards)
    result = analyze_contract(LEASE, client, jurisdiction="us_il_urbana")
    assert len(result.cards) == 27 and result.grounding.cards_verified == 27
    assert calls[0]["max_tokens"] == analyzer.DEFAULT_MAX_OUTPUT_TOKENS


def test_absent_terms_become_missing_cards_without_a_quote():
    client, _ = stub([card(1), card(18, "missing", quote="", level="low", title="没写入户通知")])
    result = analyze_contract(LEASE, client, jurisdiction="us_il_urbana")
    missing = [c for c in result.cards if c.category == "missing"]
    assert len(missing) == 1 and missing[0].clause_text == "" and missing[0].quote_match == "missing"
    assert result.grounding.cards_missing == 1 and result.grounding.cards_verified == 1
    assert result.grounding.quote_verification_rate == 1.0


@pytest.mark.parametrize("bad", [
    card(None, "missing", quote=""),   # a missing card must say which item is absent
    card(18, "missing"),               # and must not carry a quote
    card(5, "risk", quote=""),         # other cards must quote the lease
])
def test_malformed_category_cards_are_corrected_once(bad):
    client, calls = stub([bad], [card(1)])
    result = analyze_contract(LEASE, client, jurisdiction="us_il_urbana")
    assert result.attempts == 2 and len(calls) == 2
    assert "减少卡片数量" not in calls[1]["messages"][-1]["content"]


def test_illegal_without_a_supplied_statute_is_downgraded_to_verify():
    cards = [card(23, "illegal", quote="A holdover fee of $200 per day applies.", basis=["URBANA-12.5-10"]),
             card(3, "illegal", quote="Carpets must be professionally shampooed at Tenant's expense.", basis=["Made-up Act 9"])]
    client, _ = stub(cards)
    result = analyze_contract(LEASE, client, jurisdiction="us_il_urbana")
    by_item = {c.checklist_item: c for c in result.cards}
    assert by_item[23].category == "illegal" and not by_item[23].category_downgraded
    assert by_item[3].category == "verify" and by_item[3].category_downgraded and by_item[3].legal_basis == []


def test_cards_are_ordered_by_how_often_tenants_meet_them():
    cards = [card(15, "risk", quote="Monthly rent is $500."),                                  # rare
             card(23, "risk", quote="A holdover fee of $200 per day applies."),                # common
             card(7, "risk", quote="Tenant shall pay a $10 monthly portal fee.", level="low"),  # universal
             card(3, "illegal", quote="Carpets must be professionally shampooed at Tenant's expense.", basis=["URBANA-12.5-20"]),  # universal
             card(None, "risk", quote="Landlord and tenant agree.")]                          # outside the checklist
    client, _ = stub(cards)
    result = analyze_contract(LEASE, client, jurisdiction="us_il_urbana")
    assert [c.checklist_item for c in result.cards] == [3, 7, 23, 15, None]
    assert [c.tier for c in result.cards] == ["universal", "universal", "common", "rare", None]


@pytest.mark.parametrize("language, name", [("zh", "逾期不搬"), ("en", "Holdover")])
def test_checklist_names_follow_the_report_language(language, name):
    prose = {"zh": ("逾期不搬罚款", "按天罚款超过实际成本。", "要求改为实际损失。", "这份租约有多处需要核实。"),
             "en": ("Holdover penalty", "A daily penalty above actual cost.", "Ask for actual losses instead.", "Several terms need checking.")}[language]
    out = card(23, quote="A holdover fee of $200 per day applies.", title=prose[0]) | {"explanation": prose[1], "suggestion": prose[2]}

    def create(**kwargs):
        content = json.dumps({"contract_type": "lease", "risk_score": 5, "summary": prose[3], "cards": [out]})
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=content))])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    result = analyze_contract(LEASE, client, jurisdiction="us_il_urbana", output_language=language)
    assert result.cards[0].checklist_name == name


def test_output_token_limit_can_be_lowered_for_providers_with_smaller_caps(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_MAX_TOKENS", "4096")
    assert analyzer.max_output_tokens() == 4096
    monkeypatch.setenv("DEEPSEEK_MAX_TOKENS", "not a number")
    assert analyzer.max_output_tokens() == analyzer.DEFAULT_MAX_OUTPUT_TOKENS


def test_reports_saved_before_checklist_cards_still_validate():
    metadata = json.loads((REPO / "demo/fixture.json").read_text(encoding="utf-8"))
    saved = json.loads((REPO / metadata["analysis_source"]).read_text(encoding="utf-8"))["rows"][0]["result"]
    assert all("category" not in c for c in saved["cards"])
    report = AnalysisResult.model_validate(saved)
    assert all(c.category == "risk" and c.checklist_item is None for c in report.cards)

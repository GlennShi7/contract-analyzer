"""Option A (region choice = inside Urbana), absence claims checked against the text, retry reasons kept."""
import json
from pathlib import Path

import analyzer
from analyzer import absence_contradicted, analyze_contract, load_checklist
from eval import score_eval
from tests.test_checklist_cards import LEASE, card, stub

REPO = Path(__file__).resolve().parents[2]
SENTENCES = [s.strip() + "." for s in LEASE.split(".") if s.strip()]


def quoted(n):
    return [card(i + 1, quote=SENTENCES[i % len(SENTENCES)], title=f"卡片{i + 1}") for i in range(n)]


def test_urbana_choice_is_the_premise_for_illegal():
    client, calls = stub([])
    result = analyze_contract(LEASE, client, jurisdiction="us_il_urbana")
    system = calls[0]["messages"][0]["content"]
    assert "即声明房产位于 Urbana 市界内" in system and "category 用 illegal" in system
    assert "前提：房产在 Urbana 市界内" in system
    assert "按天累计或按欠款比例" in system and "单个固定服务费" in system
    assert "不得凭地址、邮编、合同自述或用户地区选择" not in system
    assert "假定房产位于 Urbana 市界内" in result.legal_scope


def test_illegal_with_an_urbana_ordinance_survives_grounding():
    holdover = "A holdover fee of $200 per day applies."
    client, _ = stub([card(23, "illegal", quote=holdover, basis=["URBANA-12.5-10"], title="逾期每天罚 $200")])
    result = analyze_contract(LEASE, client, jurisdiction="us_il_urbana")
    assert result.cards[0].category == "illegal" and not result.cards[0].category_downgraded


def test_absence_is_refused_when_the_item_does_not_take_missing_cards():
    items = load_checklist()
    assert absence_contradicted(items[15], LEASE.lower()) == "item does not take missing cards"
    assert absence_contradicted(None, LEASE.lower()) == "item does not take missing cards"


def test_absence_is_refused_when_the_contract_mentions_the_item():
    items = load_checklist()
    assert absence_contradicted(items[1], LEASE.lower()) == "contract mentions 'security deposit'"
    assert absence_contradicted(items[18], LEASE.lower()) is None  # nothing about entry in the sample lease


def test_false_absence_cards_are_blocked_and_recorded():
    # The pattern seen on a real lease: claims that utilities, casualty and move-in inspection are absent while the lease covers them.
    lease = LEASE + " Tenant pays electric and gas. Fire or other casualty may end the lease. Move-in inspection within 5 days."
    cards = quoted(10) + [card(9, "missing", quote="", level="low", title="没写水电"),
                          card(14, "missing", quote="", level="low", title="没写火灾"),
                          card(40, "missing", quote="", level="low", title="没写入住检查"),
                          card(21, "missing", quote="", level="low", title="没有自动续约"),
                          card(18, "missing", quote="", level="low", title="没写入户通知")]
    client, calls = stub(cards)
    result = analyze_contract(lease, client, jurisdiction="us_il_urbana")
    assert len(calls) == 1
    kept_missing = [c.checklist_item for c in result.cards if c.category == "missing"]
    assert kept_missing == [18]
    blocked = result.grounding.missing_blocked
    assert len(blocked) == 4 and any(b.startswith("21: item does not take") for b in blocked)
    assert any(b.startswith("14: contract mentions 'casualty'") or b.startswith("14: contract mentions 'fire'") for b in blocked)
    assert result.grounding.cards_dropped == 0  # blocked absence claims are not "failed checks" shown to readers


def test_mainland_reports_never_keep_missing_cards():
    text = "出租人和承租人约定：租金每月一千元，押金一千元。"
    client, _ = stub([card(1, "missing", quote="", level="low", title="没写")])
    result = analyze_contract(text, client, jurisdiction="cn")
    assert result.cards == [] and result.grounding.missing_blocked


def test_retry_reasons_are_kept_in_the_result():
    broken = quoted(10)
    for c in broken[:4]:
        c["category"] = "urgent"
    client, _ = stub(broken, quoted(10))
    result = analyze_contract(LEASE, client, jurisdiction="us_il_urbana")
    assert len(result.grounding.retry_reasons) == 1 and "4/10 张卡片未通过校验" in result.grounding.retry_reasons[0]


def test_summary_may_not_claim_absence_without_a_missing_card():
    client, calls = stub([])
    analyze_contract(LEASE, client, jurisdiction="us_il_urbana")
    assert "除非有对应的 missing 卡，不得在 summary 里说租约没写某事项" in calls[0]["messages"][0]["content"]


def test_item_24_is_about_lead_paint_only():
    item = load_checklist()[24]
    assert item["keywords"] == ["lead-based", "lead based", "lead paint", "lead hazard"]
    assert "租约没写不算缺失" in item["description_zh"] and "Urbana" not in item["description_zh"]


def test_category_agreement_counts_each_item_once():
    checklist = score_eval.load_checklist()
    gold = {i: "没有" for i in checklist} | {5: "违法/无效", 1: "风险"}
    cards = [{"checklist_item": 5, "category": "risk"}] * 5 + [{"checklist_item": 5, "category": "illegal"},
                                                               {"checklist_item": 1, "category": "verify"}]
    record = {"result": {"cards": cards, "grounding": {"cards_dropped": 1, "missing_blocked": ["9: x"], "retry_reasons": ["r"]}}}
    s = score_eval.score_run(record, gold, checklist, None, "r")
    assert s["category_total"] == 2 and s["category_exact"] == 1
    assert s["category_by_item"] == {1: "待核实", 5: "违法/无效"} and s["underclaim"] == []
    report = score_eval.report([s], gold, checklist, [])
    assert "没通过检查被去掉 1 张；缺失卡被关键词拦下 1 张；重试 1 次" in report


def test_frontend_explains_the_urbana_premise():
    messages = (REPO / "frontend/src/messages.js").read_text(encoding="utf-8")
    report = (REPO / "frontend/src/components/RiskReport.jsx").read_text(encoding="utf-8")
    hint = "选 Urbana 即视为房子在 Urbana 市界内，报告会据此判断是否违反市条例。Urbana 不包括 Champaign 或 Chicago；不确定时选“其他 / 不确定”。"
    assert hint in report and f"'{hint}':" in messages
    scope = analyze_contract.__globals__["ground_analysis"]  # keep the import used
    assert scope

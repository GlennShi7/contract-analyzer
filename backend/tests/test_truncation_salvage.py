"""A report that hits the output limit keeps its complete cards, and one item cannot fill the report.

On a real 48-page lease the model wrote one card per fee-schedule line (32 cards for one checklist item) until the output
limit cut the JSON, and the whole report was lost. These tests use synthetic text only.
"""
import json
from types import SimpleNamespace

import analyzer
from analyzer import analyze_contract, salvage_truncated, truncation_feedback
from tests.test_checklist_cards import LEASE, card, stub

HEAD = '{"contract_type": "lease", "risk_score": 7, "summary": "这份租约有多处需要核实。", "cards": ['


def test_complete_cards_survive_a_cut_in_the_middle_of_a_card():
    raw = HEAD + json.dumps(card(1)) + ", " + json.dumps(card(23)) + ', {"title": "截断的卡", "category": "ri'
    data = salvage_truncated(raw)
    assert data["summary"] == "这份租约有多处需要核实。" and data["risk_score"] == 7
    assert [c["checklist_item"] for c in data["cards"]] == [1, 23]


def test_salvage_reads_a_fenced_and_a_complete_report():
    complete = HEAD + json.dumps(card(1)) + "]}"
    assert len(salvage_truncated(complete)["cards"]) == 1
    assert len(salvage_truncated("```json\n" + HEAD + json.dumps(card(1)) + ",")["cards"]) == 1


def test_nothing_is_salvaged_when_the_cut_falls_inside_the_summary():
    # One retry put every fee into the summary and never reached the cards.
    assert salvage_truncated('{"contract_type": "lease", "risk_score": 8, "summary": "fees: $1,000, $200/day, $75') is None
    assert salvage_truncated(HEAD) is None
    assert salvage_truncated(None) is None


def test_retry_names_the_items_that_ran_away():
    feedback = truncation_feedback([card(3)] * 32 + [card(5)] * 9 + [card(1)])
    assert "第 3 项 32 张" in feedback and "第 5 项 9 张" in feedback and "第 1 项" not in feedback
    assert f"最多 {analyzer.PER_ITEM_CARD_CAP} 张" in feedback and "summary" in feedback


def test_one_item_keeps_its_three_strongest_cards():
    quote = "Tenant forfeits the security deposit if late."
    cards = [card(16, "risk", quote, "low"), card(16, "risk", quote, "medium"), card(16, "illegal", quote, "high", basis=["URBANA-12.5-20"]),
             card(16, "verify", quote, "high"), card(16, "risk", quote, "high"), card(1, quote=quote)]
    client, _ = stub(cards)
    result = analyze_contract(LEASE, client, jurisdiction="us_il_urbana")
    kept = [(c.category, c.risk_level) for c in result.cards if c.checklist_item == 16]
    assert kept == [("illegal", "high"), ("verify", "high"), ("risk", "high")]
    assert result.grounding.cards_capped == 2 and any(c.checklist_item == 1 for c in result.cards)


def test_cards_outside_the_checklist_are_capped_at_five():
    client, _ = stub([card(None) for _ in range(7)])
    result = analyze_contract(LEASE, client, jurisdiction="us_il_urbana")
    assert len(result.cards) == analyzer.UNLISTED_CARD_CAP and result.grounding.cards_capped == 2


def test_free_form_contracts_are_not_capped():
    quote = "押金由出租人决定是否退还。"
    output = {"contract_type": "lease", "risk_score": 7, "summary": "押金条款需要核实。",
              "cards": [card(None, quote=quote, title=f"第{i}张") for i in range(7)]}
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: SimpleNamespace(
        choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=json.dumps(output, ensure_ascii=False)))]))))
    result = analyze_contract("出租人和承租人约定：押金由出租人决定是否退还。", client, jurisdiction="cn")
    assert len(result.cards) == 7 and result.grounding.cards_capped == 0


def runaway_client(outputs):
    calls, replies = [], iter(outputs)

    def create(**kwargs):
        calls.append(kwargs | {"messages": [dict(m) for m in kwargs["messages"]]})
        content, finish = next(replies)
        return SimpleNamespace(usage=None, choices=[SimpleNamespace(finish_reason=finish, message=SimpleNamespace(content=content))])

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))), calls


def test_a_finished_retry_replaces_the_cut_off_first_attempt():
    cut = HEAD + ", ".join(json.dumps(card(3, quote="Carpets must be professionally shampooed at Tenant's expense.")) for _ in range(6)) + ', {"ti'
    finished = HEAD + json.dumps(card(1)) + "]}"
    client, calls = runaway_client([(cut, "length"), (finished, "stop")])
    result = analyze_contract(LEASE, client, jurisdiction="us_il_urbana")
    assert len(calls) == 2 and "第 3 项 6 张" in calls[1]["messages"][-1]["content"]
    assert not result.grounding.truncated and [c.checklist_item for c in result.cards] == [1]


def test_a_failed_retry_falls_back_to_the_cards_saved_from_the_first_attempt():
    cut = HEAD + json.dumps(card(1)) + ", " + json.dumps(card(23, quote="A holdover fee of $200 per day applies.")) + ', {"ti'
    summary_runaway = '{"contract_type": "lease", "risk_score": 8, "summary": "fees: $1,000, $200/day, $75'
    client, calls = runaway_client([(cut, "length"), (summary_runaway, "length")])
    result = analyze_contract(LEASE, client, jurisdiction="us_il_urbana")
    assert len(calls) == 2 and result.grounding.truncated and result.attempts == 2
    assert sorted(c.checklist_item for c in result.cards) == [1, 23]
    assert len(result.grounding.retry_reasons) == 2


def test_two_cut_off_attempts_keep_the_one_that_covers_more_items():
    first = HEAD + json.dumps(card(1)) + ", " + json.dumps(card(23, quote="A holdover fee of $200 per day applies.")) + ', {"ti'
    second = HEAD + ", ".join(json.dumps(card(3, quote="Carpets must be professionally shampooed at Tenant's expense.")) for _ in range(4)) + ', {"ti'
    client, _ = runaway_client([(first, "length"), (second, "length")])
    result = analyze_contract(LEASE, client, jurisdiction="us_il_urbana")
    assert sorted(c.checklist_item for c in result.cards) == [1, 23]

"""A long checklist report should not be lost because a few quotes miss."""
import logging

import pytest

import analyzer
from analyzer import analyze_contract
from tests.test_checklist_cards import LEASE, card, stub

SENTENCES = [s.strip() + "." for s in LEASE.split(".") if s.strip()]
FAKE = "Tenant waives every right under this lease."


def report(total, bad, *, basis_on_bad=()):
    """total quoted cards; the first `bad` quote text the lease does not contain."""
    return [card(i + 1, quote=FAKE if i < bad else SENTENCES[i % len(SENTENCES)], basis=basis_on_bad if i < bad else (),
                 title=f"卡片{i + 1}") for i in range(total)]


def test_a_few_unmatched_quotes_are_dropped_without_a_second_call(caplog):
    client, calls = stub(report(27, 3))
    with caplog.at_level(logging.WARNING, logger="analyzer"):
        result = analyze_contract(LEASE, client, jurisdiction="us_il_urbana")
    assert len(calls) == 1 and result.attempts == 1
    assert len(result.cards) == 24 and result.grounding.cards_dropped == 3
    assert all(c.verified for c in result.cards) and FAKE not in {c.clause_text for c in result.cards}
    assert "analysis_dropped_cards count=3" in caplog.text


def test_many_unmatched_quotes_retry_naming_the_cards_then_drop_what_still_misses(caplog):
    client, calls = stub(report(27, 10), report(27, 1))
    with caplog.at_level(logging.WARNING, logger="analyzer"):
        result = analyze_contract(LEASE, client, jurisdiction="us_il_urbana")
    retry = calls[1]["messages"][-1]["content"]
    assert len(calls) == 2 and "10/27 张卡片" in retry and "第 1 项《卡片1》" in retry and "第 10 项《卡片10》" in retry
    assert "第 11 项" not in retry
    assert len(result.cards) == 26 and result.grounding.cards_dropped == 1 and result.attempts == 2
    assert "analysis_attempt_failed attempt=1 finish_reason=stop" in caplog.text


def test_second_attempt_drops_a_minority_of_broken_cards():
    client, _ = stub(report(5, 5), report(5, 2))
    result = analyze_contract(LEASE, client, jurisdiction="us_il_urbana")
    assert len(result.cards) == 3 and result.grounding.cards_dropped == 2


def test_second_attempt_fails_when_most_cards_are_broken():
    # An empty or near-empty report would read as a clean lease; refuse it instead.
    client, _ = stub(report(5, 5), report(5, 3))
    with pytest.raises(analyzer.AnalysisOutputError):
        analyze_contract(LEASE, client, jurisdiction="us_il_urbana")


def test_more_cards_than_checklist_items_are_accepted():
    # Seen on a real lease: 45 cards, because one item can carry several problems.
    cards = report(45, 0)
    for i, c in enumerate(cards):
        c["checklist_item"] = (i % analyzer.CHECKLIST_SIZE) + 1
    client, calls = stub(cards)
    result = analyze_contract(LEASE, client, jurisdiction="us_il_urbana")
    assert len(calls) == 1 and len(result.cards) == 45 and result.grounding.cards_dropped == 0


def test_a_badly_formed_card_is_dropped_not_the_report(caplog):
    cards = report(27, 0)
    cards[3] = card(18, "missing", quote="Tenant forfeits the security deposit if late.", title="缺失卡却带了引文")
    cards[7]["checklist_item"] = 44
    client, calls = stub(cards)
    with caplog.at_level(logging.WARNING, logger="analyzer"):
        result = analyze_contract(LEASE, client, jurisdiction="us_il_urbana")
    assert len(calls) == 1 and len(result.cards) == 25 and result.grounding.cards_dropped == 2
    assert "analysis_rejected_cards count=2" in caplog.text and "缺失卡却带了引文" in caplog.text


def test_many_badly_formed_cards_retry_with_their_reasons():
    broken = report(10, 0)
    for c in broken[:4]:
        c["category"] = "urgent"
    client, calls = stub(broken, report(10, 0))
    result = analyze_contract(LEASE, client, jurisdiction="us_il_urbana")
    retry = calls[1]["messages"][-1]["content"]
    assert len(calls) == 2 and "4/10 张卡片未通过校验" in retry and "格式不对：第 1 张《卡片1》" in retry and "category" in retry
    assert len(result.cards) == 10 and result.grounding.cards_dropped == 0


def test_a_runaway_card_list_is_still_rejected():
    client, calls = stub(report(101, 0), report(101, 0))
    with pytest.raises(analyzer.AnalysisOutputError):
        analyze_contract(LEASE, client, jurisdiction="us_il_urbana")
    assert len(calls) == 2


def test_a_small_report_with_a_bad_quote_still_retries():
    client, calls = stub(report(3, 1), report(3, 0))
    result = analyze_contract(LEASE, client, jurisdiction="us_il_urbana")
    assert len(calls) == 2 and result.grounding.cards_dropped == 0 and len(result.cards) == 3


def test_dropped_cards_take_their_citations_with_them():
    client, _ = stub(report(27, 2, basis_on_bad=["URBANA-12.5-10"]))
    result = analyze_contract(LEASE, client, jurisdiction="us_il_urbana")
    assert result.grounding.cards_dropped == 2
    assert "URBANA-12.5-10" not in {law.id for law in result.legal_sources}
    assert result.grounding.law_references_total == 0


def test_truncated_output_is_logged_with_its_reason(caplog):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        from types import SimpleNamespace
        return SimpleNamespace(usage=SimpleNamespace(completion_tokens=32768),
                               choices=[SimpleNamespace(finish_reason="length", message=SimpleNamespace(content='{"contract_type": "lease"'))])

    from types import SimpleNamespace
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    with caplog.at_level(logging.WARNING, logger="analyzer"), pytest.raises(analyzer.AnalysisOutputError):
        analyze_contract(LEASE, client, jurisdiction="us_il_urbana")
    assert caplog.text.count("finish_reason=length completion_tokens=32768") == 2


def test_english_reports_get_word_limits_and_room_to_finish():
    client, calls = stub([], [])  # the stub writes Chinese prose, so both attempts fail the language check
    with pytest.raises(analyzer.AnalysisOutputError):
        analyze_contract(LEASE, client, jurisdiction="us_il_urbana", output_language="en")
    system = calls[0]["messages"][0]["content"]
    assert "explanation under 40 words" in system and calls[0]["max_tokens"] == 16384


def test_warnings_reach_the_console_without_logging_setup():
    # uvicorn configures only its own loggers; Python's last-resort handler prints WARNING and above to stderr.
    logger = logging.getLogger("analyzer")
    assert logger.getEffectiveLevel() <= logging.WARNING

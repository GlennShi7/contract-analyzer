"""Fixes from the second batch of real runs: runaways, Urbana applicability, absence list, no-action cards, cut qualifiers."""
import json
from types import SimpleNamespace

import pytest

import analyzer
from analyzer import absence_candidates, analyze_contract, complete_qualified_quote, trim_summary
from eval import run_eval
from tests.test_checklist_cards import LEASE, card, stub

EXCULPATION = ("The Lessor shall not be liable for any damage or injury occasioned by water or any other damages howsoever caused, "
               "nor shall the Lessor be responsible for any accident resulting from any cause whatsoever, unless caused by Lessor's negligence. "
               "Rent is due on the first.")


def system_prompt(text=LEASE, **kwargs):
    client, calls = stub([])
    analyze_contract(text, client, jurisdiction="us_il_urbana", **kwargs)
    return calls[0]["messages"][0]["content"]


def test_urbana_applicability_is_stated_precisely():
    system = system_prompt()
    assert "第 12.5 章没有楼栋单位数或房龄门槛" in system and "1994 年 4 月 1 日" in system
    assert "合同没有显示属于这些情形，就按适用处理" in system
    # The old wording made unit count and building age look like Urbana conditions.
    assert "除市界以外的适用条件（单位数、房龄、签约时间、例外）" not in system
    assert "逐条注意地域、单位数量、房龄" not in system


def test_absence_list_is_computed_before_the_call():
    assert 1 not in absence_candidates(LEASE)  # the sample lease mentions a security deposit
    system = system_prompt()
    listed = absence_candidates(LEASE)
    assert f"只有清单第 {'、'.join(map(str, listed))} 项可以出 category 为 missing 的卡片" in system
    example = json.loads(system.split("JSON 示例：", 1)[1].split("\n", 1)[0])
    assert [c["checklist_item"] for c in example["cards"] if c["category"] == "missing"] == listed[:1]


def test_a_lease_that_addresses_every_item_gets_no_absence_cards():
    keywords = " ".join(item["keywords"][0] for item in analyzer.load_checklist().values())
    text = LEASE + " " + keywords
    assert absence_candidates(text) == []
    system = system_prompt(text)
    assert "这份合同不出 missing 卡" in system
    example = json.loads(system.split("JSON 示例：", 1)[1].split("\n", 1)[0])
    assert all(c["category"] != "missing" for c in example["cards"])


def test_prompt_discourages_non_finding_cards_and_bounds_the_count():
    system = system_prompt()
    assert "不写“无需处理 / No action needed”这类卡片" in system and "卡片总数一般不超过 40 张" in system


def test_no_action_cards_are_removed():
    sentence = [s.strip() + "." for s in LEASE.split(".") if s.strip()][0]
    filler = card(5, quote=sentence, title="没问题")
    filler["suggestion"] = "No action needed."
    client, _ = stub([card(1, quote=sentence, title="真问题"), filler])
    result = analyze_contract(LEASE, client, jurisdiction="us_il_urbana")
    assert [c.title for c in result.cards] == ["真问题"] and result.grounding.no_action_removed == 1


def test_quote_cut_before_a_qualifier_is_completed():
    cut = "The Lessor shall not be liable for any damage or injury occasioned by water or any other damages howsoever caused"
    full = complete_qualified_quote(cut, EXCULPATION)
    assert full.endswith("unless caused by Lessor's negligence.") and full in EXCULPATION
    # Line breaks in the extracted PDF text between the quote's words.
    wrapped = EXCULPATION.replace("any other damages howsoever", "any other\ndamages howsoever").replace("unless caused", "unless\ncaused")
    full = complete_qualified_quote(cut, wrapped)
    assert full.endswith("unless caused by Lessor's negligence.") and "\n" not in full
    assert analyzer.match_quote(full, wrapped)[0] == "whitespace"
    # No qualifier in the rest of the sentence: unchanged.
    assert complete_qualified_quote("Rent is due", EXCULPATION) == "Rent is due"


def test_completed_quote_is_what_the_reader_sees_and_still_verified():
    text = LEASE + " " + EXCULPATION
    cut = "The Lessor shall not be liable for any damage or injury occasioned by water or any other damages howsoever caused"
    client, _ = stub([card(11, quote=cut, title="宽泛免责")])
    result = analyze_contract(text, client, jurisdiction="us_il_urbana")
    assert result.cards[0].clause_text.endswith("unless caused by Lessor's negligence.") and result.cards[0].verified


def test_overlong_summary_is_trimmed_not_fatal():
    summary = ("This lease has many fees. " * 120).strip()
    assert len(summary) > 2000
    trimmed = trim_summary(summary)
    assert len(trimmed) <= 2000 and trimmed.endswith(".")

    def create(**kwargs):
        reply = {"contract_type": "lease", "risk_score": 5, "summary": "这份租约" + "费用很多。" * 500, "cards": []}
        return SimpleNamespace(usage=None, choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=json.dumps(reply, ensure_ascii=False)))])
    long_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    result = analyze_contract(LEASE, long_client, jurisdiction="us_il_urbana")
    assert len(result.summary) <= 2000 and result.attempts == 1


def test_output_budget_leaves_room_for_a_full_english_report():
    # A completed 47-card English report on a 48-page lease used about 6,100 output tokens.
    assert 8000 <= analyzer.DEFAULT_MAX_OUTPUT_TOKENS <= 12000


def test_failed_generations_keep_their_raw_text(tmp_path, pdf_factory):
    def runaway(**kwargs):
        return SimpleNamespace(usage=SimpleNamespace(completion_tokens=16384),
                               choices=[SimpleNamespace(finish_reason="length", message=SimpleNamespace(content='{"cards": [{"title": "x"'))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=runaway)))
    with pytest.raises(analyzer.AnalysisOutputError) as caught:
        analyze_contract(LEASE, client, jurisdiction="us_il_urbana")
    assert caught.value.raw_outputs == ['{"cards": [{"title": "x"', '{"cards": [{"title": "x"']

    pdf = tmp_path / "lease.pdf"
    pdf.write_bytes(pdf_factory([LEASE]))
    paths = run_eval.run(pdf, client, jurisdiction="us_il_urbana", runs=1, out_dir=tmp_path / "out")
    record = json.loads(paths[0].read_text(encoding="utf-8"))
    assert record["raw_outputs_saved"] == 2
    assert sorted(p.name for p in (tmp_path / "out").glob("*_raw.txt")) == ["lease_full_run1_attempt1_raw.txt", "lease_full_run1_attempt2_raw.txt"]

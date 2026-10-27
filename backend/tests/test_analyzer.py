from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from analyzer import (
    AnalysisOutputError, GeneratedAnalysis, MAX_CARDS, analyze_contract, classify_contract,
    ground_analysis, load_laws, match_quote, model_name, parse_analysis,
)


def sample_output(kind="lease"):
    return {"contract_type": kind, "risk_score": 7, "summary": "押金条款需要核实。", "cards": [
        {"title": "押金扣减", "clause_text": "押金由出租人决定是否退还。", "risk_level": "high",
         "explanation": "应核实扣减条件与依据。", "legal_basis": ["住房租赁条例-10"], "suggestion": "签前确认退还时间与扣减条件。"}
    ]}


def stub_client(outputs):
    calls = []
    iterator = iter(outputs)

    def create(**kwargs):
        # Copy messages, because the production correction path appends to its list.
        calls.append(kwargs | {"messages": [dict(message) for message in kwargs["messages"]]})
        content, finish = next(iterator)
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish, message=SimpleNamespace(content=content))])

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))), calls


def test_classifier_keeps_illinois_lease_out_of_chinese_law_library():
    assert classify_contract("出租人甲，承租人乙，租金按月支付，押金。") == "lease"
    assert classify_contract("用人单位与劳动者订立劳动合同，工资及试用期。") == "labor"
    english = (Path(__file__).resolve().parents[1] / "eval/contracts/lease_en.txt").read_text(encoding="utf-8")
    assert classify_contract(english) == "other"
    assert classify_contract("Illinois 出租人和承租人约定租金。") == "other"


def test_official_law_library_is_complete_for_selected_sources():
    labor, tenancy = load_laws("labor"), load_laws("lease")
    assert len(labor) == len(tenancy) == 24
    articles = {law.id: law for law in (*labor, *tenancy)}
    assert len(articles) == 48
    assert "不得超过二年" in articles["劳动合同法-24"].text
    assert "但是当事人另有约定的除外" in articles["民法典-712"].text
    assert "无正当理由不得扣减押金" in articles["住房租赁条例-10"].text
    for law in articles.values():
        assert sha256(law.text.encode()).hexdigest() == law.text_sha256
        assert law.source_url.startswith("https://www.samr.gov.cn/")


def test_json_and_code_fence_parse_to_the_same_schema():
    raw = json.dumps(sample_output(), ensure_ascii=False)
    assert parse_analysis(raw) == parse_analysis("```json\n" + raw + "\n```")


@pytest.mark.parametrize("change", [
    {"risk_score": 11}, {"risk_score": True}, {"risk_score": "7"},
    {"summary": " "}, {"cards": [{"risk_level": "urgent"}]}, {"invented": "field"},
    {"cards": sample_output()["cards"] * (MAX_CARDS + 1)},
])
def test_schema_rejects_missing_invalid_and_extra_fields(change):
    with pytest.raises(ValidationError):
        parse_analysis(json.dumps(sample_output() | change))


@pytest.mark.parametrize("raw", [None, "", "not json", "[]"])
def test_unusable_output_is_rejected(raw):
    with pytest.raises(ValueError):
        parse_analysis(raw)


def test_quote_checks_do_not_verify_near_matches_with_changed_meaning():
    text = "出租人不得无故扣减押金。"
    assert match_quote(text, text) == ("exact", 1.0)
    assert match_quote("出租人不得\n无故扣减押金。", text) == ("whitespace", 1.0)
    assert match_quote("", text) == ("missing", 0.0)
    # A one-character semantic change may score highly; it must still remain unverified.
    generated = GeneratedAnalysis.model_validate(sample_output())
    generated.cards[0].clause_text = "押金由出租人决定是否退还！"
    report = ground_analysis(generated, "押金由出租人决定是否退还。", load_laws("lease"), model="test", attempts=1)
    assert report.cards[0].quote_match == "approximate"
    assert report.cards[0].verified is False
    assert match_quote("Tenant must\npay rent.", "Tenant must pay rent.") == ("whitespace", 1.0)
    assert match_quote("Tenant is notable.", "Tenant is not able.")[0] not in {"exact", "whitespace"}


def test_changed_negation_is_never_verified():
    generated = GeneratedAnalysis.model_validate(sample_output())
    generated.cards[0].clause_text = "出租人可以无故扣减乙方已经支付的全部押金。"
    report = ground_analysis(generated, "出租人不得无故扣减乙方已经支付的全部押金。", (), model="test", attempts=1)
    assert not report.cards[0].verified


def test_invalid_risk_level_is_rejected_even_with_all_other_fields_present():
    output = sample_output()
    output["cards"][0]["risk_level"] = "urgent"
    with pytest.raises(ValidationError) as error:
        parse_analysis(json.dumps(output))
    assert error.value.errors()[0]["loc"] == ("cards", 0, "risk_level")


def test_grounding_filters_unknown_ids_and_reports_pre_filter_counts():
    generated = GeneratedAnalysis.model_validate(sample_output())
    generated.cards[0].legal_basis += ["编造法条-999", "住房租赁条例-10"]
    report = ground_analysis(generated, generated.cards[0].clause_text, load_laws("lease"), model="test", attempts=1)
    assert report.cards[0].legal_basis == ["住房租赁条例-10"]
    assert report.grounding.law_references_total == 3
    assert report.grounding.law_references_valid == 2
    assert report.grounding.law_reference_validity_rate == pytest.approx(2 / 3)
    assert report.grounding.quote_verification_rate == 1
    assert [law.id for law in report.legal_sources] == ["住房租赁条例-10"]


def test_empty_cards_and_no_citations_are_not_reported_as_100_percent():
    generated = GeneratedAnalysis.model_validate(sample_output() | {"cards": []})
    report = ground_analysis(generated, "contract", (), model="test", attempts=1)
    assert report.grounding.quote_verification_rate is None
    assert report.grounding.law_reference_validity_rate is None


def test_json_mode_injects_only_the_selected_law_group():
    client, calls = stub_client([(json.dumps(sample_output()), "stop")])
    report = analyze_contract("出租人和承租人约定：押金由出租人决定是否退还。", client, jurisdiction="cn")
    sent = calls[0]
    assert sent["response_format"] == {"type": "json_object"}
    assert sent["extra_body"] == {"thinking": {"type": "disabled"}}
    assert "住房租赁条例-10" in sent["messages"][0]["content"]
    assert f"至多{MAX_CARDS}个重要风险" in sent["messages"][0]["content"]
    assert "劳动合同法-19" not in sent["messages"][0]["content"]
    assert report.cards[0].verified is True


def test_unknown_jurisdiction_does_not_inject_chinese_statutes():
    client, calls = stub_client([(json.dumps(sample_output()), "stop")])
    report = analyze_contract("出租人和承租人约定押金。", client)
    assert "住房租赁条例-10" not in calls[0]["messages"][0]["content"]
    assert not report.legal_sources
    assert report.cards[0].legal_basis == []
    assert "未注入" in report.legal_scope


def test_invalid_json_is_corrected_once():
    client, calls = stub_client([("bad", "stop"), (json.dumps(sample_output()), "stop")])
    report = analyze_contract("出租人和承租人约定押金。", client)
    assert len(calls) == report.attempts == 2
    assert "未通过校验" in calls[1]["messages"][-1]["content"]


@pytest.mark.parametrize("output,finish", [("{}", "stop"), (None, "stop"), (json.dumps(sample_output()), "length")])
def test_two_invalid_responses_stop_without_a_third_call(output, finish):
    client, calls = stub_client([(output, finish), (output, finish)])
    with pytest.raises(AnalysisOutputError):
        analyze_contract("出租人和承租人约定押金。", client)
    assert len(calls) == 2


def test_model_is_configurable_without_a_key_in_source(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_MODEL", "test-model")
    assert model_name() == "test-model"
    monkeypatch.setenv("DEEPSEEK_MODEL", " ")
    assert model_name() == "deepseek-flash"


def test_labor_analysis_injects_labor_sources_only():
    output = sample_output("labor")
    output["cards"][0]["clause_text"] = "试用期为六个月。"
    output["cards"][0]["legal_basis"] = ["劳动合同法-19"]
    client, calls = stub_client([(json.dumps(output), "stop")])
    report = analyze_contract("用人单位与劳动者约定，试用期为六个月。", client, jurisdiction="cn")
    system = calls[0]["messages"][0]["content"]
    assert "劳动合同法-19" in system
    assert "住房租赁条例-10" not in system
    assert report.cards[0].verified


def test_live_analysis_requires_explicit_flag(monkeypatch):
    import sys
    import main
    from eval.analysis_eval import main as run_live_eval

    def forbidden():
        raise AssertionError("No API client should be created without --live")

    monkeypatch.setattr(main, "get_llm_client", forbidden)
    monkeypatch.setattr(sys, "argv", ["analysis_eval"])
    with pytest.raises(SystemExit) as error:
        run_live_eval()
    assert error.value.code == 2

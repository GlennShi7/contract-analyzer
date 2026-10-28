from datetime import date
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

import analyzer
from analyzer import LawArticle, analyze_contract, jurisdiction_conflict, load_laws
from test_analyzer import sample_output, stub_client


def test_urbana_profile_has_three_government_levels_and_traceable_city_text():
    laws = load_laws("lease", "us_il_urbana")
    assert len(laws) == 43
    assert {level: sum(law.authority_level == level for law in laws) for level in ("municipal", "state", "federal")} == {"municipal": 21, "state": 15, "federal": 7}
    assert all(law.jurisdiction == "us_il_urbana" for law in laws)
    city = {law.id: law for law in laws if law.authority_level == "municipal"}
    assert city["URBANA-12.5-10"].source_row == "Sheet1!E577"
    assert "Automatically renewing" in city["URBANA-12.5-10"].text
    assert "carpet cleaning" in city["URBANA-12.5-20"].text
    assert "twenty-four" in city["URBANA-12.5-15"].text or "twenty four" in city["URBANA-12.5-15"].text
    assert not any(law.id == "765 ILCS 705/35" for law in laws)
    assert not any(law.id.startswith("765 ILCS 720") for law in laws)


def test_state_and_federal_limits_remain_in_the_supplied_text():
    laws = {law.id: law for law in load_laws("lease", "us_il_urbana")}
    assert "25 or more" in laws["765 ILCS 715/1"].text
    assert "public housing" in laws["765 ILCS 715/3"].text
    assert "owner-occupied" in laws["765 ILCS 742/10"].text
    assert "prior to 1978" in laws["42 U.S.C. 4851b(27)"].text
    assert "nothing" in laws["42 U.S.C. 4852d(c)"].text.lower()
    assert "5 or more units" not in laws["765 ILCS 710/1"].text
    assert "may not" in laws["765 ILCS 710/1"].text


def test_jurisdiction_choice_does_not_follow_document_language():
    text = (Path(__file__).resolve().parents[1] / "eval/contracts/lease_en.txt").read_text(encoding="utf-8")
    assert jurisdiction_conflict(text, "cn")
    assert not jurisdiction_conflict(text, "us_il_urbana")
    assert load_laws("labor", "us_il_urbana") == ()
    assert load_laws("lease", "unknown") == ()


def test_urbana_pipeline_injects_local_state_and_federal_sources():
    text = "Residential Lease. Landlord and Tenant. Property located at 1 Main Street, Urbana, Illinois. Security deposit."
    client, calls = stub_client([(json.dumps(sample_output()), "stop")])
    result = analyze_contract(text, client, jurisdiction="us_il_urbana")
    system = calls[0]["messages"][0]["content"]
    for law_id in ("URBANA-12.5-10", "765 ILCS 710/1", "42 U.S.C. 3604"):
        assert law_id in system
    assert "劳动合同法-19" not in system
    assert "住房租赁条例-10" not in system
    assert result.cards[0].legal_basis == []  # The fabricated CN citation in the stub is removed.
    assert "Urbana, Illinois" in result.legal_scope


@pytest.mark.parametrize("city", ["Chicago", "Champaign", "Evanston"])
def test_other_illinois_city_is_not_treated_as_urbana(city):
    text = f"Residential Lease. Landlord and Tenant. Property located at 1 Main Street, {city}, Illinois."
    client, calls = stub_client([(json.dumps(sample_output()), "stop")])
    report = analyze_contract(text, client, jurisdiction="us_il_urbana")
    assert "URBANA-12.5-10" not in calls[0]["messages"][0]["content"]
    assert not report.legal_sources
    assert "不一致" in report.legal_scope


def test_future_expired_and_unverified_articles_are_excluded(monkeypatch, tmp_path):
    template = load_laws("lease", "us_il_urbana")[0].model_dump(mode="json")
    rows = [template | {"id": "active"},
            template | {"id": "future", "effective_from": "2027-01-01"},
            template | {"id": "expired", "effective_until": "2026-10-28"},
            template | {"id": "unverified", "source_status": "historical_unverified"}]
    (tmp_path / "tenancy_us_il_urbana.json").write_text(json.dumps(rows), encoding="utf-8")
    monkeypatch.setattr(analyzer, "LAWS_DIR", tmp_path)
    load_laws.cache_clear()
    try:
        assert [row.id for row in load_laws("lease", "us_il_urbana")] == ["active"]
        assert [row.id for row in load_laws("lease", "us_il_urbana", as_of=date(2027, 1, 1))] == ["active", "future"]
    finally:
        load_laws.cache_clear()


@pytest.mark.parametrize("url", ["http://www.ilga.gov/example", "https://uscode.house.gov.evil.example/law", "https://user@uscode.house.gov/example", "https://example.com/law"])
def test_legal_sources_reject_untrusted_urls(url):
    template = load_laws("lease", "us_il_urbana")[0].model_dump(mode="json")
    with pytest.raises(ValidationError):
        LawArticle.model_validate(template | {"source_url": url})

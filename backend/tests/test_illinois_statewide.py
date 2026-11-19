"""Illinois outside Urbana: state and federal law only, never Urbana ordinance."""
import json
from pathlib import Path

import pytest

import analyzer
from analyzer import analyze_contract, jurisdiction_conflict, load_laws
from tests.test_checklist_cards import LEASE, card, stub

REPO = Path(__file__).resolve().parents[2]
SCOPE = "伊利诺伊州住宅租赁：只含伊利诺伊州法和联邦法参考，不含任何城市条例（Champaign、Chicago 等城市的租赁条例未收录）。各条有单位数量、房龄、签订时间等适用条件，需逐条核对。"


def test_statewide_library_is_the_urbana_library_without_its_ordinance():
    urbana = load_laws("lease", "us_il_urbana")
    statewide = load_laws("lease", "us_il")
    assert {law.id for law in statewide} == {law.id for law in urbana if law.authority_level in {"state", "federal"}}
    assert statewide and all(law.jurisdiction == "us_il" and law.authority_level != "municipal" for law in statewide)
    assert not any(law.id.startswith("URBANA") for law in statewide)
    # The Urbana load is untouched by the statewide copy.
    assert {law.jurisdiction for law in load_laws("lease", "us_il_urbana")} == {"us_il_urbana"}
    assert load_laws("labor", "us_il") == () and load_laws("other", "us_il") == ()


@pytest.mark.parametrize("text, conflict", [
    ("Premises located at 505 E Green St, Champaign, IL 61820", False),
    ("Property address: 10 N State St, Chicago, Illinois", False),
    ("Property address: 123 Example St, Urbana, Illinois", False),
    ("Premises located at a house in Peoria", False),
    ("Property address: 100 Kirkwood Ave, Bloomington, IN 47401", True),
    ("Premises located at 5 Main St, New York, NY 10001", True),
    ("本合同适用中华人民共和国法律。", True),
])
def test_only_addresses_outside_illinois_conflict(text, conflict):
    assert jurisdiction_conflict(text, "us_il") is conflict


def test_champaign_lease_is_a_conflict_for_urbana_but_fine_statewide():
    text = LEASE + " Premises located at 505 E Green St, Champaign, IL 61820."
    assert jurisdiction_conflict(text, "us_il_urbana") and not jurisdiction_conflict(text, "us_il")


def test_prompt_offers_state_law_only_and_forbids_city_ordinances():
    client, calls = stub([])
    result = analyze_contract(LEASE, client, jurisdiction="us_il")
    system = calls[0]["messages"][0]["content"]
    laws = json.loads(system.split("可引用的法条：", 1)[1])
    assert laws and not any(law["id"].startswith("URBANA") or law["authority_level"] == "municipal" for law in laws)
    assert "没有提供任何城市条例" in system and "不能标 illegal" in system
    assert "逐项检查以下 43 项清单" in system and "禁止套用芝加哥" not in system
    assert result.legal_scope == SCOPE


def test_citing_urbana_ordinance_statewide_cannot_make_a_card_illegal():
    holdover = "A holdover fee of $200 per day applies."
    client, _ = stub([card(23, "illegal", quote=holdover, basis=["URBANA-12.5-10"], title="逾期每天罚 $200"),
                      card(11, "illegal", basis=["765 ILCS 705/1"], title="免除房东过失责任")])
    result = analyze_contract(LEASE, client, jurisdiction="us_il")
    by_item = {c.checklist_item: c for c in result.cards}
    assert by_item[23].category == "verify" and by_item[23].category_downgraded and by_item[23].legal_basis == []
    assert by_item[11].category == "illegal" and by_item[11].legal_basis == ["765 ILCS 705/1"]
    assert [s.id for s in result.legal_sources] == ["765 ILCS 705/1"]
    assert result.legal_sources[0].jurisdiction == "us_il"


def test_api_accepts_the_statewide_region(api, pdf_factory):
    client, calls = api
    doc = client.post("/upload", files={"file": ("lease.pdf", pdf_factory(LEASE))}).json()
    response = client.post("/analyze", json={"doc_id": doc["doc_id"], "jurisdiction": "us_il"})
    assert response.status_code == 200
    assert response.json()["result"]["legal_scope"] == SCOPE
    assert "没有提供任何城市条例" in calls[-1]["messages"][0]["content"]
    assert client.post("/analyze", json={"doc_id": doc["doc_id"], "jurisdiction": "us_il_champaign"}).status_code == 422


def test_frontend_offers_and_translates_the_statewide_region():
    report = (REPO / "frontend/src/components/RiskReport.jsx").read_text(encoding="utf-8")
    messages = (REPO / "frontend/src/messages.js").read_text(encoding="utf-8")
    assert '<option value="us_il">' in report and "jurisdiction === 'us_il'" in report
    for key in (SCOPE, "美国 · 伊利诺伊州（Urbana 以外，如 Champaign）",
                "只用伊利诺伊州法和联邦法；Champaign、Chicago 等城市条例未收录。房子在 Urbana 请选上一项。"):
        assert f"'{key}':" in messages

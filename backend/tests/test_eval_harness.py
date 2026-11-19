import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from eval import run_eval, score_eval

REPO = Path(__file__).resolve().parents[2]


def stub_client(cards):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        from analyzer import classify_contract
        text = json.loads(kwargs["messages"][1]["content"])["contract_text"]
        content = json.dumps({"contract_type": classify_contract(text), "risk_score": 5, "summary": "测试摘要", "cards": cards})
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=content))])

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))), calls


LEASE_PAGE = "Residential lease. Landlord and tenant agree. Monthly rent is 500. Security deposit is 500. A holdover fee of 200 per day applies."
PAMPHLET = "Protect Your Family From Lead in Your Home. EPA pamphlet. What is lead? It is a metal. What can I do? Test your home."


def test_oregon_sized_lease_passes_the_upload_limit(api, pdf_factory):
    # A 48-page Urbana lease with required pamphlets extracts to about 120,000 characters.
    client, _ = api
    pages = [("Tenant shall pay rent. " * 130)[:3000] for _ in range(40)]
    response = client.post("/upload", files={"file": ("long.pdf", pdf_factory(pages))})
    assert response.status_code == 200, response.text


def test_limit_messages_match_frontend_translations():
    messages = REPO / "frontend/src/messages.js"
    upload = REPO / "frontend/src/components/Upload.jsx"
    if not messages.exists():
        pytest.skip("frontend sources are not in this checkout")
    import main
    import parser
    keys = messages.read_text(encoding="utf-8")
    # Backend error text doubles as the translation key; a changed number silently breaks English.
    assert f"'合同文字超过 {main.MAX_DOCUMENT_CHARS} 字符，请拆分后重新上传再分析'" in keys
    assert f"'提取文字超过 {parser.MAX_DOCUMENT_CHARS} 字符，请拆分 PDF 后上传'" in keys
    assert f"提取文字 {parser.MAX_DOCUMENT_CHARS} 字符" in upload.read_text(encoding="utf-8")
    assert f"{parser.MAX_DOCUMENT_CHARS:,} extracted characters" in keys


def test_informational_pages_are_detected_but_signed_forms_are_kept():
    assert run_eval.is_informational_page(PAMPHLET)
    assert not run_eval.is_informational_page(LEASE_PAGE)
    assert not run_eval.is_informational_page(PAMPHLET + " Lessor's Disclosure. By signing below you acknowledge.")
    text, dropped = run_eval.build_text([LEASE_PAGE, PAMPHLET, LEASE_PAGE], drop_info_pages=True)
    assert dropped == [2] and "EPA" not in text and text.count("Residential lease") == 2
    text, dropped = run_eval.build_text([LEASE_PAGE, PAMPHLET], drop_info_pages=False)
    assert dropped == [] and "EPA" in text


def test_run_eval_saves_every_run_and_records_failures(tmp_path, pdf_factory):
    pdf = tmp_path / "lease.pdf"
    pdf.write_bytes(pdf_factory([LEASE_PAGE, PAMPHLET]))
    client, calls = stub_client([])
    paths = run_eval.run(pdf, client, jurisdiction="us_il_urbana", runs=2, out_dir=tmp_path / "out", drop_info_pages=True)
    assert [p.name for p in paths] == ["lease_noinfo_run1.json", "lease_noinfo_run2.json"]
    record = json.loads(paths[0].read_text(encoding="utf-8"))
    assert record["pages_dropped"] == [2] and record["result"]["cards"] == [] and "error" not in record
    assert "EPA" not in json.loads(calls[0]["messages"][1]["content"])["contract_text"]

    def broken(**kwargs):
        raise TimeoutError("provider timed out")
    failing = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=broken)))
    paths = run_eval.run(pdf, failing, jurisdiction="us_il_urbana", runs=1, out_dir=tmp_path / "out")
    assert "TimeoutError" in json.loads(paths[0].read_text(encoding="utf-8"))["error"]


def card(item=None, category=None, quote="A holdover fee of 200 per day applies.", basis=()):
    out = {"title": "t", "clause_text": quote, "risk_level": "high", "explanation": "e", "legal_basis": list(basis), "suggestion": "s"}
    if item is not None:
        out["checklist_item"] = item
    if category is not None:
        out["category"] = category
    return out


GOLD = {23: "违法/无效", 5: "风险", 2: "没有", 12: "没问题", 18: "缺失"}


def test_score_counts_hits_misses_false_positives_and_severity():
    checklist = score_eval.load_checklist()
    record = {"result": {"cards": [card(23, "risk", basis=["URBANA-12.5-10"]), card(12, "risk"), card(5, "illegal")]}}
    s = score_eval.score_run(record, GOLD, checklist, None, "r1")
    assert s["should"] == 3 and s["hits"] == [5, 23] and s["misses"] == [18]
    assert s["false_positives"] == [12] and s["recall"] == pytest.approx(2 / 3)
    assert s["overclaim"] == [5] and s["underclaim"] == [23]
    assert s["illegal_hits_with_law"] == 1 and s["illegal_hits"] == 1
    assert s["recall_by_tier"]["common"] == (2, 3)


def test_score_uses_mapping_for_cards_without_item_numbers(tmp_path):
    checklist = score_eval.load_checklist()
    record = {"result": {"cards": [card(), card(quote="Rent is 500.")]}}
    unmapped = score_eval.score_run(record, GOLD, checklist, None, "r.json")
    assert unmapped["unmapped_cards"] == [0, 1] and unmapped["hits"] == []
    run = tmp_path / "r.json"
    run.write_text(json.dumps(record), encoding="utf-8")
    template = tmp_path / "map.json"
    score_eval.write_mapping([run], checklist, template)
    mapping = json.loads(template.read_text(encoding="utf-8"))
    assert mapping["r.json"][0]["items"][0] == 23  # keyword suggestion from the quote
    mapping["r.json"][1]["items"] = []  # a finding outside the checklist
    s = score_eval.score_run(record, GOLD, checklist, mapping, "r.json")
    assert s["hits"] == [23] and s["other_cards"] == 1 and s["unmapped_cards"] == []


def test_gold_from_report_csv_prefers_person_label_and_tracks_unconfirmed(tmp_path):
    path = tmp_path / "gold.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        w = csv.writer(handle)
        w.writerow(["租约", "项", "名称", "命中", "页码", "初稿", "判断", "已核对", "备注"])
        w.writerow(["x.pdf", "12", "维修责任", "3", "5", "风险", "没问题", "是", ""])
        w.writerow(["x.pdf", "23", "逾期不搬", "1", "25", "违法/无效", "违法/无效", "", ""])
    labels, unconfirmed = score_eval.load_gold(path)
    assert labels == {12: "没问题", 23: "违法/无效"} and unconfirmed == [23]


def test_report_summarises_stability_across_runs():
    checklist = score_eval.load_checklist()
    runs = [score_eval.score_run({"result": {"cards": cards}}, GOLD, checklist, None, f"r{i}")
            for i, cards in enumerate([[card(23), card(5)], [card(23)]], 1)]
    runs.append(score_eval.score_run({"error": "Timeout"}, GOLD, checklist, None, "r3"))
    text = score_eval.report(runs, GOLD, checklist, [])
    assert "平均召回 50%" in text and "时有时无：5. 其他杂费、罚款和催收费（1/2）" in text
    assert "每次都漏：18. 房东入户" in text and "运行失败：Timeout" in text

"""Phase 1 of the per-item pipeline: clause segments with pages, and the candidates each checklist item gets.

Synthetic text only; the real-lease numbers come from eval.checklist_retrieval_eval run on a private copy.
"""
import json

import pytest

from analyzer import load_checklist
from eval.checklist_retrieval_eval import parse_pages, score
from retrieval import retrieve_items
from segmenter import PAGE_SEPARATOR, is_informational_page, segment_pages, segment_text

DEPOSIT = ("1.4 SECURITY DEPOSIT\nLessee agrees to pay a security deposit to Lessor which, if necessary, will be forfeited and applied "
           "to the costs of repairing damages, cleaning charges, rent due, or attorney's fees incurred by Lessor in enforcing the lease.\n"
           "Any portion of said deposit not forfeited shall be returned within 30 days of the end of the lease.")
PARKING = ("2.5 PARKING\nParking permits are issued yearly for the lot behind the building and must be displayed at all times.\n1. Lessor will not be responsible for any damages incurred to Lessee's vehicle.\n"
           "2. Double parking is not allowed and vehicles will be towed at the owner's expense.")
INSURANCE = ("1.6 INSURANCE\nLessee is responsible for obtaining insurance for fire, theft and liability. Lessor is not liable for any loss "
             "unless caused by Lessor's negligence. Liability coverage must name the owner. Liability limits apply. The negligence of "
             "guests is the Lessee's liability.")
FEES = "General Repairs\n" + "\n".join(f"Replace Item {i} ${10 + i}.00" for i in range(40))
PAMPHLET = ("Protect Your Family From Lead in Your Home. What is lead-based paint? EPA guidance. What happens if the landlord "
            "does not disclose? The tenant may ask for a copy. This ordinance applies to all units.")


def lease_pages():
    return [DEPOSIT + "\n" + INSURANCE, PARKING, FEES, PAMPHLET]


def test_segments_point_at_the_joined_text_and_know_their_pages():
    pages = lease_pages()
    segments = segment_pages(pages)
    text = PAGE_SEPARATOR.join(pages)
    assert all(text[s.start:s.end] == s.text for s in segments)
    deposit = next(s for s in segments if s.heading == "1.4 SECURITY DEPOSIT")
    assert deposit.pages == [1] and "returned within 30 days" in deposit.text
    assert next(s for s in segments if s.heading == "1.6 INSURANCE").pages == [1]


def test_numbered_sub_items_remember_their_section():
    segments = segment_pages([PARKING + "\n" + DEPOSIT])
    sub = next(s for s in segments if s.text.startswith("1. Lessor will not be responsible"))
    assert sub.section == "2.5 PARKING"


def test_fee_tables_are_cut_into_groups_and_price_rows_are_not_headings():
    segments = [s for s in segment_pages(lease_pages()) if 3 in s.pages]
    assert len(segments) >= 2 and all(s.text.count("\n") < 23 for s in segments)
    assert not any(s.heading and "$" in s.heading for s in segments)


def test_a_lone_heading_joins_the_clause_after_it_and_scraps_join_the_one_before():
    segments = segment_pages(["ARTICLE IV - RENT\n" + "Rent is due on the first day of each month and is payable to Lessor. " * 4])
    assert len(segments) == 1 and segments[0].text.startswith("ARTICLE IV")
    segments = segment_pages([DEPOSIT + "\nInitials: ____", INSURANCE])
    assert [s.heading for s in segments] == ["1.4 SECURITY DEPOSIT", "1.6 INSURANCE"] and segments[0].pages == [1]


def test_pamphlet_and_ordinance_summary_pages_are_marked():
    assert is_informational_page(PAMPHLET)
    assert not is_informational_page(DEPOSIT)
    # Ordinance summaries say "the landlord shall" in lower case; leases capitalize their defined terms.
    summary = "(A) If the tenant refuses access, the landlord may obtain relief. (B) In an emergency the landlord may enter."
    assert is_informational_page(summary)
    assert not is_informational_page("The Landlord shall give 24 hours notice. The Tenant may request repairs.")
    assert [s.informational for s in segment_pages(lease_pages()) if 4 in s.pages] == [True]


def test_text_without_page_breaks_has_no_page_numbers():
    assert all(s.pages == [] for s in segment_text(DEPOSIT + "\n\n" + PARKING))


def by_id(results):
    return {result.item["id"]: result for result in results}


def test_one_specific_phrase_outranks_two_generic_ones():
    results = by_id(retrieve_items(segment_pages(lease_pages()), load_checklist()))
    hits = results[11].hits
    parking = next(i for i, h in enumerate(hits) if "not be responsible" in h.keywords)
    assert parking <= 1 and "1. Lessor will not be responsible" in hits[parking].segment.text


def test_keywords_match_at_word_starts():
    segments = segment_pages(["4.1 SUBLETTING\nLessee shall not engage in subletting of the premises without written consent. " * 3])
    assert by_id(retrieve_items(segments, load_checklist()))[19].hits[0].keywords


def test_pamphlet_segments_are_used_only_when_nothing_else_matches():
    results = by_id(retrieve_items(segment_pages(lease_pages()), load_checklist()))
    assert not any(h.segment.informational for h in results[1].hits)
    lead_only = by_id(retrieve_items(segment_pages([PARKING, PAMPHLET]), load_checklist()))[24]
    assert lead_only.hits and all(h.segment.informational for h in lead_only.hits)


def test_absence_follows_the_keyword_rule():
    checklist = load_checklist()
    missing_type = next(i for i, item in checklist.items() if item["absent_means"] == "missing")
    other = next(i for i, item in checklist.items() if item["absent_means"] != "missing")
    segments = segment_pages(["Rent is payable monthly. " * 20])
    results = by_id(retrieve_items(segments, {missing_type: checklist[missing_type], other: checklist[other]}))
    assert results[missing_type].status == "absent" and results[other].status == "no_match"


def test_candidates_respect_the_count_and_length_budget():
    pages = [f"{i}.1 DEPOSIT CLAUSE {i}\n" + "The security deposit is refundable as stated here. " * 12 for i in range(1, 20)]
    results = by_id(retrieve_items(segment_pages(pages), load_checklist(), top_k=8, max_chars=2000))
    assert 1 <= len(results[1].hits) <= 8 and sum(len(h.segment.text) for h in results[1].hits) <= 2000


def test_an_extra_ranking_fills_in_after_keyword_hits():
    segments = segment_pages(lease_pages())
    fee_index = next(i for i, s in enumerate(segments) if 3 in s.pages)
    results = by_id(retrieve_items(segments, load_checklist(), extra_rankings={11: [fee_index]}))
    ids = [h.segment.id for h in results[11].hits]
    assert segments[fee_index].id in ids
    assert all(h.keywords for h in results[11].hits[:ids.index(segments[fee_index].id)])


def test_recall_is_scored_against_key_pages():
    assert parse_pages("2, 6，31") == {2, 6, 31} and parse_pages("") == set() and parse_pages([4]) == {4}
    segments = segment_pages(lease_pages())
    results = retrieve_items(segments, load_checklist())
    key = {"1": {"j": "风险", "pages": "1"}, "11": {"j": "违法/无效", "pages": "2"}, "2": {"j": "没有", "pages": ""}}
    report = score(results, segments, key, [3, 8])
    assert report["summary"]["problem_items"]["n"] == 2 and report["summary"]["problem_items"]["hit@8"] == 1.0
    assert report["summary"]["absence"]["key_absent"] == [2]


@pytest.fixture
def lease_pdf(pdf_factory):
    return pdf_factory(["1.4 SECURITY DEPOSIT Lessee pays a security deposit that will be forfeited for cleaning charges.",
                        "2.5 PARKING Lessor will not be responsible for any damages incurred to Lessee's vehicle."])


def test_retrieve_endpoint_returns_candidates_with_pages_and_no_model_call(api, lease_pdf):
    client, calls = api
    doc_id = client.post("/upload", files={"file": ("lease.pdf", lease_pdf, "application/pdf")}).json()["doc_id"]
    response = client.post("/retrieve", json={"doc_id": doc_id})
    assert response.status_code == 200 and not calls
    body = response.json()
    assert body["pages_known"] and body["pages_total"] == 2 and len(body["items"]) == len(load_checklist())
    item1 = next(item for item in body["items"] if item["id"] == 1)
    first = body["segments"][item1["hits"][0]["segment"]]
    assert item1["status"] == "found" and first["pages"] == [1] and "security deposit" in first["text"]
    item11 = next(item for item in body["items"] if item["id"] == 11)
    assert any(body["segments"][hit["segment"]]["pages"] == [2] for hit in item11["hits"])


def test_documents_uploaded_before_pages_were_stored_still_retrieve(api, monkeypatch):
    import documents
    import main
    client, _ = api
    monkeypatch.setattr(main, "contract_text", lambda doc_id: DEPOSIT)
    monkeypatch.setattr(main, "load_pages", lambda doc_id: None)
    body = client.post("/retrieve", json={"doc_id": "c" * 64}).json()
    assert body["pages_known"] is False and all(s["pages"] == [] for s in body["segments"].values())
    assert documents.load_pages("d" * 64) is None


def test_retrieve_rejects_unknown_documents_and_bad_sizes(api):
    client, calls = api
    assert client.post("/retrieve", json={"doc_id": "e" * 64}).status_code == 404
    assert client.post("/retrieve", json={"doc_id": "e" * 64, "top_k": 50}).status_code == 422
    assert not calls


def test_pages_file_round_trips(monkeypatch, tmp_path):
    import documents
    monkeypatch.setattr(documents, "DATA_DIR", tmp_path)
    documents.save_document("f" * 64, "a\n\nb", ["a", "b"])
    assert documents.load_pages("f" * 64) == ["a", "b"] and documents.load_document("f" * 64) == "a\n\nb"
    (tmp_path / ("f" * 64 + ".pages.json")).write_text(json.dumps({"bad": 1}), encoding="utf-8")
    assert documents.load_pages("f" * 64) is None

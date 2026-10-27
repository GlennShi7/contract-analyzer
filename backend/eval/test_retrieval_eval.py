"""Unit tests for the scoring in retrieval_eval.py (no model needed): python -m pytest eval -q"""
import pytest

from eval.retrieval_eval import chunk_spans, covers, is_hit, load_data, random_hit_rate


def test_chunk_spans_follow_the_sliding_window():
    text = "abcdefghij"
    assert chunk_spans(text, ["abcd", "cdef", "efgh", "ghij", "ij"]) == [(0, 4), (2, 6), (4, 8), (6, 10), (8, 10)]
    assert chunk_spans(text, ["ABCD"]) is None              # chunker rewrote the text


def test_a_chunk_must_cover_half_of_the_answer():
    answer = (10, 20)
    assert covers((0, 15), answer)                          # 5 of 10 characters
    assert not covers((0, 14), answer)                      # 4 of 10
    assert covers((12, 40), answer)                         # 8 of 10


def test_is_hit_accepts_any_listed_answer():
    q = {"answer": ["x", "y"], "spans": [(0, 4), (50, 54)]}
    assert is_hit("....", (48, 60), q)
    assert not is_hit("....", (10, 40), q)
    assert is_hit("has y in it", None, q)                   # containment fallback


def test_random_baseline():
    assert random_hit_rate(10, 1, 3) == pytest.approx(0.3)
    assert random_hit_rate(10, 0, 3) == 0
    assert random_hit_rate(2, 1, 5) == 1


def test_every_answer_sentence_occurs_exactly_once():
    contracts, questions = load_data()                      # raises if an answer is missing or ambiguous
    assert len(questions) == 56 and set(contracts) == {"lease_zh", "labor_zh", "lease_en"}

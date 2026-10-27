import pytest

from chunker import chunk_text


def test_overlap_preserves_boundaries_and_short_tail():
    assert chunk_text("abcdefghij", 4, 2) == ["abcd", "cdef", "efgh", "ghij", "ij"]
    assert chunk_text("") == []
    assert chunk_text("abc", 4, 0) == ["abc"]


@pytest.mark.parametrize("size,overlap", [(0, 0), (4, -1), (4, 4), (4, 5)])
def test_invalid_parameters_cannot_create_an_infinite_loop(size, overlap):
    with pytest.raises(ValueError):
        chunk_text("contract", size, overlap)

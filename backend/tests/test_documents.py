import pytest

import documents


def test_saved_text_survives_another_read(monkeypatch, tmp_path):
    monkeypatch.setattr(documents, "DATA_DIR", tmp_path / "data")
    doc_id = "a" * 64
    documents.save_document(doc_id, "合同全文\n第二页")
    assert documents.load_document(doc_id) == "合同全文\n第二页"
    documents.save_document(doc_id, "替换后的全文")
    assert documents.load_document(doc_id) == "替换后的全文"
    assert len(list(documents.DATA_DIR.iterdir())) == 1


@pytest.mark.parametrize("doc_id", ["../private", "a" * 63, "A" * 64, "a" * 64 + "\n"])
def test_invalid_document_id_cannot_be_a_path(doc_id):
    with pytest.raises(ValueError):
        documents.document_path(doc_id)

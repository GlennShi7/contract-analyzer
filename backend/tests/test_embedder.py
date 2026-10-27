from embedder import search_chunks, store_chunks


def test_search_excludes_other_and_legacy_documents(collection):
    store_chunks(["A deposit", "A rent"], "a", collection=collection)
    store_chunks(["B deposit", "B rent"], "b", collection=collection)
    collection.add(ids=["legacy"], documents=["unscoped deposit"])
    found = search_chunks("deposit", "a", n_results=3, collection=collection)
    assert len(found) == 2
    assert {row["doc_id"] for row in found} == {"a"}
    assert {row["text"] for row in found} == {"A deposit", "A rent"}
    assert search_chunks("deposit", "missing", collection=collection) == []


def test_reindex_replaces_content_and_removes_stale_chunks(collection):
    store_chunks(["old 1", "old 2", "old 3"], "a", collection=collection)
    store_chunks(["other"], "b", collection=collection)
    assert store_chunks(["new"], "a", collection=collection) == 1
    assert store_chunks(["new"], "a", collection=collection) == 1
    assert collection.count() == 2
    assert search_chunks("old", "a", collection=collection) == [{"text": "new", "doc_id": "a", "chunk": 0}]

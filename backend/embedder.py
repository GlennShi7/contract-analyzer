from functools import lru_cache
import logging
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
DATABASE_DIR = Path(__file__).resolve().parent / "chroma_db"
logger = logging.getLogger(__name__)


class EmbeddingUnavailableError(RuntimeError):
    """The configured local embedding model could not be initialized."""


@lru_cache(maxsize=1)
def get_embedding_function():
    try:
        return embedding_functions.SentenceTransformerEmbeddingFunction(model_name=MODEL_NAME)
    except (OSError, RuntimeError, ValueError) as exc:
        logger.exception("Embedding model initialization failed")
        raise EmbeddingUnavailableError("Local embedding model unavailable") from exc


@lru_cache(maxsize=1)
def get_collection():
    client = chromadb.PersistentClient(path=str(DATABASE_DIR))
    return client.get_or_create_collection(
        name="contracts", embedding_function=get_embedding_function()
    )


def store_chunks(chunks: list[str], doc_id: str, *, collection=None):
    if not chunks:
        raise ValueError("Cannot index an empty document")
    if collection is None:
        collection = get_collection()

    existing = collection.get(where={"doc_id": doc_id}, include=[])["ids"]
    ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
    collection.upsert(
        documents=chunks,
        ids=ids,
        metadatas=[{"doc_id": doc_id, "chunk": i} for i in range(len(chunks))],
    )
    stale_ids = sorted(set(existing) - set(ids))
    if stale_ids:
        collection.delete(ids=stale_ids)
    return len(chunks)


def search_chunks(query: str, doc_id: str, n_results: int = 3, *, collection=None):
    if n_results < 1:
        raise ValueError("n_results must be positive")
    if collection is None:
        collection = get_collection()
    # Count only this document, including when its index contains fewer than k chunks.
    ids = collection.get(where={"doc_id": doc_id}, include=[])["ids"]
    if not ids:
        return []
    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, len(ids)),
        where={"doc_id": doc_id},
        include=["documents", "metadatas"],
    )
    return [
        {"text": text, "doc_id": metadata["doc_id"], "chunk": metadata["chunk"]}
        for text, metadata in zip(results["documents"][0], results["metadatas"][0])
    ]

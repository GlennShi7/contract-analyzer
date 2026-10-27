"""Persist extracted contract text independently of the vector index."""
from pathlib import Path
import os
import re
import tempfile

DATA_DIR = Path(__file__).resolve().parent / "data"
DOC_ID_PATTERN = r"^[0-9a-f]{64}$"


def document_path(doc_id: str) -> Path:
    if re.fullmatch(DOC_ID_PATTERN, doc_id) is None:
        raise ValueError("Invalid document ID")
    return DATA_DIR / f"{doc_id}.txt"


def save_document(doc_id: str, text: str) -> None:
    path = document_path(doc_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(text)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_document(doc_id: str) -> str:
    return document_path(doc_id).read_text(encoding="utf-8")

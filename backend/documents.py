"""Persist extracted contract text independently of the vector index."""
from pathlib import Path
import json
import os
import re
import tempfile

DATA_DIR = Path(__file__).resolve().parent / "data"
DOC_ID_PATTERN = r"^[0-9a-f]{64}$"


def document_path(doc_id: str) -> Path:
    if re.fullmatch(DOC_ID_PATTERN, doc_id) is None:
        raise ValueError("Invalid document ID")
    return DATA_DIR / f"{doc_id}.txt"


def pages_path(doc_id: str) -> Path:
    return document_path(doc_id).with_suffix(".pages.json")


def save_document(doc_id: str, text: str, pages: list[str] | None = None) -> None:
    """Save the joined text; with pages, also the per-page text so segments can carry page numbers."""
    if pages is not None:
        write_atomically(pages_path(doc_id), json.dumps(pages, ensure_ascii=False))
    write_atomically(document_path(doc_id), text)


def write_atomically(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(content)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_document(doc_id: str) -> str:
    return document_path(doc_id).read_text(encoding="utf-8")


def load_pages(doc_id: str) -> list[str] | None:
    """Per-page text, or None for documents uploaded before pages were stored."""
    try:
        pages = json.loads(pages_path(doc_id).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    return pages if isinstance(pages, list) and all(isinstance(page, str) for page in pages) else None

from pathlib import Path
import json
import sys
from types import SimpleNamespace
from uuid import uuid4

import chromadb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ConstantEmbedding(chromadb.EmbeddingFunction):
    """Make all chunks equally similar so only metadata can isolate documents."""
    def __init__(self):
        pass

    def __call__(self, input):
        return [[1.0, 0.0] for _ in input]

    @staticmethod
    def name():
        return "constant-test-embedding"

    def get_config(self):
        return {}

    @staticmethod
    def build_from_config(config):
        return ConstantEmbedding()


@pytest.fixture
def collection():
    client = chromadb.EphemeralClient()
    result = client.create_collection("test_" + uuid4().hex, embedding_function=ConstantEmbedding())
    yield result
    client.delete_collection(result.name)


@pytest.fixture
def api(monkeypatch, tmp_path, collection):
    import documents
    import embedder
    import main
    from fastapi.testclient import TestClient

    monkeypatch.setattr(documents, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(embedder, "get_collection", lambda: collection)
    calls = []

    def complete(**kwargs):
        calls.append(kwargs)
        if kwargs.get("response_format"):
            from analyzer import classify_contract
            text = json.loads(kwargs["messages"][1]["content"])["contract_text"]
            content = json.dumps({"contract_type": classify_contract(text), "risk_score": 5,
                                  "summary": "Test summary", "cards": []})
        else:
            content = "Test answer"
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=content))])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=complete)))
    monkeypatch.setattr(main, "get_llm_client", lambda: client)
    with TestClient(main.app) as test_client:
        yield test_client, calls


@pytest.fixture
def pdf_factory():
    def make_pdf(text):
        # Minimal real PDF: use the actual PDF parser in endpoint tests, without extra dependencies.
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("ascii")
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        ]
        data = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for i, obj in enumerate(objects, start=1):
            offsets.append(len(data))
            data.extend(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
        xref = len(data)
        data.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
        for offset in offsets[1:]:
            data.extend(f"{offset:010d} 00000 n \n".encode())
        data.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
        return bytes(data)
    return make_pdf

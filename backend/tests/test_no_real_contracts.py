"""Guard: real contracts and anything built from them must never be committed.

Checks what git tracks, so it also catches files someone force-adds past .gitignore.
"""
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
# The only contract document allowed is the synthetic demo lease, plus README screenshots of that demo.
# Add a file here only after checking it shows no real contract.
ALLOWED_DOCUMENTS = {
    "demo/lease_en.pdf",
    "docs/images/demo-overview.png", "docs/images/demo-questions.png",
    "docs/images/workspace-desktop.png", "docs/images/workspace-mobile.png",
}
DOCUMENT_SUFFIXES = {".pdf", ".docx", ".doc", ".png", ".jpg", ".jpeg", ".heic"}
FORBIDDEN_PARTS = ("eval/private/", "_初稿.json", "关键词报告", "keyword_hits")


def tracked_files() -> list[str]:
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=REPO, capture_output=True, check=True).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    return [name for name in out.decode("utf-8").split("\0") if name]


def test_no_contract_documents_are_tracked():
    documents = [f for f in tracked_files() if Path(f).suffix.lower() in DOCUMENT_SUFFIXES and f not in ALLOWED_DOCUMENTS
                 and not f.startswith(("frontend/public/", "frontend/src/assets/"))]
    assert documents == [], f"Contract-like documents are tracked; remove them from git: {documents}"


def test_no_private_eval_material_is_tracked():
    private = [f for f in tracked_files() if any(part in f for part in FORBIDDEN_PARTS)]
    assert private == [], f"Private evaluation material is tracked; remove it from git: {private}"


def test_gitignore_keeps_real_contracts_out():
    rules = (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
    for rule in ("backend/eval/private/", "*.pdf", "!demo/lease_en.pdf", "*_初稿.json"):
        assert rule in rules

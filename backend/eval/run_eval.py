"""Run the analyzer on one real lease several times and save every result for scoring.

Real leases contain personal information. Outputs go to backend/eval/private/ (git-ignored) by default.

    cd backend
    python -m eval.run_eval ~/leases/lease_a.pdf --jurisdiction us_il_urbana --runs 3
    # A/B check: the same lease without pamphlet and ordinance-summary pages
    python -m eval.run_eval ~/leases/lease_a.pdf --jurisdiction us_il_urbana --runs 3 --drop-info-pages

Each run file holds the full analysis (or the error), the model, timing and which pages were sent.
Score the files with eval.score_eval.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import time

from analyzer import AnalysisOutputError, analyze_contract, model_name
from parser import extract_pages

BACKEND = Path(__file__).resolve().parents[1]
PRIVATE = Path(__file__).resolve().parent / "private"
# Pamphlets and question-and-answer summaries repeat statutes; they are not lease terms.
INFO_MARKERS = re.compile(r"protect your family|\bepa\b|radon guide|iema|what (?:happens|if|is|are|can|does)\b[^?]{0,120}\?", re.I)
SIGNED_FORM = re.compile(r"lessor's disclosure|tenant's acknowledgment|lessee's acknowledgment|by signing below", re.I)


def is_informational_page(text: str) -> bool:
    """Two or more pamphlet markers, and not a disclosure form that the tenant signs."""
    if SIGNED_FORM.search(text):
        return False
    return len(INFO_MARKERS.findall(text)) >= 2


def build_text(pages: list[str], *, drop_info_pages: bool) -> tuple[str, list[int]]:
    dropped = [i for i, page in enumerate(pages, 1) if drop_info_pages and is_informational_page(page)]
    kept = [page for i, page in enumerate(pages, 1) if i not in dropped]
    return "\n\n".join(kept), dropped


def deepseek_client():
    from dotenv import load_dotenv
    from openai import OpenAI
    load_dotenv(BACKEND / ".env")
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise SystemExit("DEEPSEEK_API_KEY is not set (backend/.env or environment).")
    return OpenAI(api_key=key, base_url="https://api.deepseek.com", timeout=300, max_retries=0)


def run(pdf: Path, client, *, jurisdiction: str, runs: int, out_dir: Path, drop_info_pages: bool = False,
        model: str | None = None, **analyze_kwargs) -> list[Path]:
    pages = extract_pages(str(pdf))
    text, dropped = build_text(pages, drop_info_pages=drop_info_pages)
    label = "noinfo" if drop_info_pages else "full"
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for i in range(1, runs + 1):
        started = time.monotonic()
        record = {
            "lease": pdf.name, "run": i, "variant": label, "jurisdiction": jurisdiction,
            "model": model or model_name(), "options": analyze_kwargs,
            "pages_total": len(pages), "pages_dropped": dropped, "chars_sent": len(text),
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            result = analyze_contract(text, client, jurisdiction=jurisdiction, model=model, **analyze_kwargs)
            record["result"] = result.model_dump(mode="json")
        except AnalysisOutputError as error:
            record["error"] = f"AnalysisOutputError: {error.__cause__ or error}"
            # What the model wrote, for diagnosing runaways; contains contract quotes, so it stays in the output folder.
            for number, raw in enumerate(error.raw_outputs, 1):
                if raw:
                    (out_dir / f"{pdf.stem}_{label}_run{i}_attempt{number}_raw.txt").write_text(raw, encoding="utf-8")
            record["raw_outputs_saved"] = sum(1 for raw in error.raw_outputs if raw)
        except Exception as error:  # network or provider failure: keep the run, record why it failed
            record["error"] = f"{type(error).__name__}: {error}"
        record["elapsed_s"] = round(time.monotonic() - started, 1)
        path = out_dir / f"{pdf.stem}_{label}_run{i}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        written.append(path)
        status = "error: " + record["error"][:120] if "error" in record else f"{len(record['result']['cards'])} cards"
        print(f"run {i}/{runs}: {status} ({record['elapsed_s']}s) -> {path}")
    return written


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--jurisdiction", default="us_il_urbana")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--out", type=Path, default=PRIVATE)
    ap.add_argument("--drop-info-pages", action="store_true", help="remove pamphlet and ordinance-summary pages before analysis")
    ap.add_argument("--model")
    ap.add_argument("--language", choices=["zh", "en"], default="zh", help="language of the report prose")
    a = ap.parse_args()
    run(a.pdf, deepseek_client(), jurisdiction=a.jurisdiction, runs=a.runs, out_dir=a.out,
        drop_info_pages=a.drop_info_pages, model=a.model, output_language=a.language)


if __name__ == "__main__":
    main()

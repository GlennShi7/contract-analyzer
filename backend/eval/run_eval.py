"""Run the analyzer on one real lease several times and save every result for scoring.

Real leases contain personal information. Outputs go to backend/eval/private/ (git-ignored) by default.

    cd backend
    python -m eval.run_eval ~/leases/lease_a.pdf --jurisdiction us_il_urbana --runs 3
    # A/B check: the same lease without pamphlet and ordinance-summary pages
    python -m eval.run_eval ~/leases/lease_a.pdf --jurisdiction us_il_urbana --runs 3 --drop-info-pages
    # the per-item review (about 40 calls per run)
    python -m eval.run_eval ~/leases/lease_a.pdf --jurisdiction us_il_urbana --runs 3 --pipeline per_item

Each run file holds the full analysis (or the error), the model, timing and which pages were sent.
Score the files with eval.score_eval.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

from analyzer import AnalysisOutputError, analyze_contract, model_name
from per_item import analyze_contract_per_item
from parser import extract_pages
from segmenter import is_informational_page  # noqa: F401  re-exported for the tests and callers

BACKEND = Path(__file__).resolve().parents[1]
PRIVATE = Path(__file__).resolve().parent / "private"
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
        model: str | None = None, pipeline: str = "single", **analyze_kwargs) -> list[Path]:
    pages = extract_pages(str(pdf))
    text, dropped = build_text(pages, drop_info_pages=drop_info_pages)
    kept_pages = [page for number, page in enumerate(pages, 1) if number not in dropped]
    label = ("noinfo" if drop_info_pages else "full") + ("_peritem" if pipeline == "per_item" else "")
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for i in range(1, runs + 1):
        started = time.monotonic()
        record = {
            "lease": pdf.name, "run": i, "variant": label, "jurisdiction": jurisdiction,
            "model": model or model_name(), "options": analyze_kwargs | {"pipeline": pipeline},
            "pages_total": len(pages), "pages_dropped": dropped, "chars_sent": len(text),
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            if pipeline == "per_item":
                # Page numbers then refer to the kept pages; with --drop-info-pages they shift.
                result = analyze_contract_per_item(text, client, pages=kept_pages, jurisdiction=jurisdiction, model=model, **analyze_kwargs)
            else:
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
    ap.add_argument("--pipeline", choices=["single", "per_item"], default="single",
                    help="single: whole contract in one call; per_item: one call per checklist item on its retrieved segments")
    a = ap.parse_args()
    run(a.pdf, deepseek_client(), jurisdiction=a.jurisdiction, runs=a.runs, out_dir=a.out,
        drop_info_pages=a.drop_info_pages, model=a.model, pipeline=a.pipeline, output_language=a.language)


if __name__ == "__main__":
    main()

"""Retrieval recall of the per-item pipeline (phase 1): for each checklist item, do the top-k segments reach the pages
a human marked as relevant?

Real leases and their answer keys contain personal information: pass them from outside the repository, and write any
output under backend/eval/private/ (git-ignored).

    cd backend
    python -m eval.checklist_retrieval_eval ~/leases/lease_a.pdf ~/leases/lease_a_key.json
    python -m eval.checklist_retrieval_eval ~/leases/lease_a.pdf ~/leases/lease_a_key.json --k 3 5 8 --show 5

The answer key is a JSON object {"items": {"1": {"j": "风险", "pages": "2,6"}, ...}} with 1-based PDF page numbers;
j is one of 违法/无效, 风险, 待核实, 没问题, 没有. Items with empty pages are skipped for recall; items judged 没有 (the
lease does not address them) are compared with the retrieval's absence decision.
"""
import argparse
import json
from math import comb
from pathlib import Path

from analyzer import load_checklist
from parser import extract_pages
from retrieval import retrieve_items
from segmenter import segment_pages

PROBLEM = {"违法/无效", "风险", "待核实"}


def parse_pages(value) -> set[int]:
    if isinstance(value, list):
        return {int(v) for v in value}
    return {int(part) for part in str(value or "").replace("，", ",").split(",") if part.strip()}


def random_hit_rate(n_segments: int, n_relevant: int, k: int) -> float:
    k = min(k, n_segments)
    if n_relevant <= 0:
        return 0.0
    return 1 - comb(n_segments - n_relevant, k) / comb(n_segments, k)


def score(results, segments, key_items: dict, ks: list[int]) -> dict:
    by_id = {r.item["id"]: r for r in results}
    rows = []
    for item_id, retrieval in by_id.items():
        gold = key_items.get(str(item_id))
        if not gold:
            continue
        pages = parse_pages(gold.get("pages"))
        row = {"id": item_id, "name": retrieval.item["name_zh"], "gold": gold.get("j"), "gold_pages": sorted(pages),
               "status": retrieval.status, "absent_means": retrieval.item["absent_means"]}
        if pages:
            relevant = sum(1 for s in segments if set(s.pages) & pages)
            for k in ks:
                top = retrieval.hits[:k]
                touched = set().union(*(set(h.segment.pages) for h in top)) if top else set()
                row[f"hit@{k}"] = bool(touched & pages)
                row[f"pages@{k}"] = len(touched & pages) / len(pages)
                row[f"random@{k}"] = random_hit_rate(len(segments), relevant, k)
            row["retrieved_pages"] = [h.segment.pages for h in retrieval.hits[:max(ks)]]
        rows.append(row)

    def mean(values):
        values = list(values)
        return round(sum(values) / len(values), 3) if values else None

    summary = {"segments": len(segments)}
    for label, chosen in (("problem_items", [r for r in rows if r["gold"] in PROBLEM and r["gold_pages"]]),
                          ("items_with_pages", [r for r in rows if r["gold_pages"]])):
        block = {"n": len(chosen)}
        for k in ks:
            block[f"hit@{k}"] = mean(r[f"hit@{k}"] for r in chosen)
            block[f"pages@{k}"] = mean(r[f"pages@{k}"] for r in chosen)
            block[f"random@{k}"] = mean(r[f"random@{k}"] for r in chosen)
        block["misses@5" if 5 in ks else f"misses@{ks[-1]}"] = [r["id"] for r in chosen if not r[f"hit@{5 if 5 in ks else ks[-1]}"]]
        summary[label] = block
    absent_gold = {r["id"] for r in rows if r["gold"] == "没有"}
    absent_tool = {r["id"] for r in rows if r["status"] == "absent"}
    summary["absence"] = {
        "tool_absent": sorted(absent_tool), "key_absent": sorted(absent_gold),
        "agree": sorted(absent_tool & absent_gold),
        "tool_absent_but_key_has_text": sorted(absent_tool - absent_gold),
        "key_absent_tool_found_text": sorted(i for i in absent_gold - absent_tool if by_id[i].status == "found"),
    }
    return {"summary": summary, "rows": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("pdf", type=Path)
    parser.add_argument("key", type=Path)
    parser.add_argument("--k", type=int, nargs="+", default=[3, 5, 8])
    parser.add_argument("--show", type=int, default=0, help="print the retrieved pages for this many top segments per missed item")
    parser.add_argument("--out", type=Path, help="write the full result as JSON (put it under backend/eval/private/)")
    args = parser.parse_args(argv)
    pages = extract_pages(str(args.pdf))
    segments = segment_pages(pages)
    ks = sorted(set(args.k))
    results = retrieve_items(segments, load_checklist(), top_k=max(ks))
    key = json.loads(args.key.read_text(encoding="utf-8"))
    report = score(results, segments, key["items"], ks)
    s = report["summary"]
    print(f"{len(pages)} 页，切成 {s['segments']} 段")
    for label, title in (("problem_items", "初稿判为有问题的项"), ("items_with_pages", "初稿标了页码的所有项")):
        b = s[label]
        line = "；".join(f"top{k} 命中 {b[f'hit@{k}']:.0%}（随机 {b[f'random@{k}']:.0%}），页码覆盖 {b[f'pages@{k}']:.0%}" for k in ks)
        print(f"{title}（{b['n']} 项）：{line}")
        misses = next(v for key_name, v in b.items() if key_name.startswith("misses@"))
        print(f"  没命中：{misses or '无'}")
    a = s["absence"]
    print(f"缺失判断：工具判缺 {a['tool_absent']}；初稿判“没有” {a['key_absent']}；一致 {a['agree']}；"
          f"工具判缺但初稿说有文字 {a['tool_absent_but_key_has_text']}；初稿说没有但关键词找到了 {a['key_absent_tool_found_text']}")
    if args.show:
        for row in report["rows"]:
            if row["gold_pages"] and not row.get(f"hit@{max(ks)}"):
                print(f"  第 {row['id']} 项 {row['name']}：初稿页 {row['gold_pages']}，检索到 {row['retrieved_pages'][:args.show]}")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"已保存 {args.out}")


if __name__ == "__main__":
    main()

"""Score saved analysis runs against a lease's answer key (one label per checklist item).

    cd backend
    # cards already carry checklist_item (step 3 onward): scoring is automatic
    python -m eval.score_eval --gold private/lease_a_gold.csv --runs private/lease_a_full_run*.json
    # older outputs without checklist_item: write a mapping template, confirm it, then score
    python -m eval.score_eval --gold private/lease_a_gold.csv --runs private/*.json --write-mapping private/map.json
    python -m eval.score_eval --gold private/lease_a_gold.csv --runs private/*.json --mapping private/map.json

Answer key formats:
- CSV exported from the keyword report ("导出 CSV"): uses the 判断 column, falls back to 初稿.
- JSON draft: {"items": {"1": {"j": "风险"}, ...}}.

Labels: 违法/无效, 风险, 待核实, 缺失 = the tool should raise the item; 没问题, 没有 = it should not.
"""
import argparse
import csv
import json
from pathlib import Path
import re
from statistics import mean

CHECKLIST = Path(__file__).resolve().parents[1] / "checklist.json"
SHOULD_FLAG = {"违法/无效", "风险", "待核实", "缺失"}
SHOULD_NOT = {"没问题", "没有"}
CATEGORY_LABEL = {"illegal": "违法/无效", "risk": "风险", "verify": "待核实", "missing": "缺失"}
TIER_ZH = {"universal": "每人都会", "common": "常见", "rare": "罕见"}
# An item with several cards is judged by its strongest claim.
STRENGTH = ["illegal", "risk", "verify", "missing"]


def load_checklist(path: Path = CHECKLIST) -> dict[int, dict]:
    return {item["id"]: item for item in json.loads(path.read_text(encoding="utf-8"))["items"]}


def load_gold(path: Path) -> tuple[dict[int, str], list[int]]:
    """Return {item: label} and the items whose label was not confirmed by a person."""
    if path.suffix.lower() == ".csv":
        labels, unconfirmed = {}, []
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                label = (row.get("判断") or row.get("初稿") or "").strip()
                if label:
                    labels[int(row["项"])] = label
                    if row.get("已核对", "").strip() != "是":
                        unconfirmed.append(int(row["项"]))
        return labels, unconfirmed
    data = json.loads(path.read_text(encoding="utf-8"))
    labels = {int(k): v["j"] for k, v in data["items"].items() if v.get("j")}
    return labels, sorted(labels)  # a draft is unconfirmed by definition


def keyword_suggestions(card: dict, checklist: dict[int, dict], top: int = 2) -> list[int]:
    blob = " ".join(str(card.get(k, "")) for k in ("clause_text", "title", "explanation")).lower()
    scores = {}
    for item_id, item in checklist.items():
        score = sum(len(re.findall(r"\b" + re.escape(kw.lower()), blob)) * (len(item["keywords"]) - rank)
                    for rank, kw in enumerate(item["keywords"]))
        if score:
            scores[item_id] = score
    return [item_id for item_id, _ in sorted(scores.items(), key=lambda kv: -kv[1])[:top]]


def card_items(card: dict, index: int, run_name: str, mapping: dict | None) -> list[int] | None:
    if isinstance(card.get("checklist_item"), int):
        return [card["checklist_item"]]
    if mapping and run_name in mapping:
        for entry in mapping[run_name]:
            if entry["card"] == index:
                return [int(x) for x in entry.get("items") or []]
    return None


def score_run(record: dict, gold: dict[int, str], checklist: dict[int, dict], mapping: dict | None, run_name: str) -> dict:
    if "error" in record:
        return {"run": run_name, "error": record["error"]}
    cards = record["result"]["cards"]
    should = {i for i, label in gold.items() if label in SHOULD_FLAG}
    should_not = {i for i, label in gold.items() if label in SHOULD_NOT}
    flagged, unmapped, other, by_item = set(), [], 0, {}
    for index, card in enumerate(cards):
        items = card_items(card, index, run_name, mapping)
        if items is None:
            unmapped.append(index)
        elif not items:
            other += 1
        for item in items or []:
            flagged.add(item)
            by_item.setdefault(item, []).append(card)
    hits = flagged & should
    out = {
        "run": run_name, "cards": len(cards), "unmapped_cards": unmapped, "other_cards": other,
        "should": len(should), "hits": sorted(hits), "misses": sorted(should - flagged),
        "false_positives": sorted(flagged & should_not), "recall": len(hits) / len(should) if should else None,
        "recall_by_tier": {},
    }
    for tier in TIER_ZH:
        tier_should = {i for i in should if checklist[i]["tier"] == tier}
        if tier_should:
            out["recall_by_tier"][tier] = (len(tier_should & flagged), len(tier_should))
    # One verdict per checklist item, so an item with five cards counts once.
    item_category = {}
    for item in hits:
        categories = [c.get("category") for c in by_item[item] if c.get("category") in CATEGORY_LABEL]
        if categories:
            item_category[item] = min(categories, key=STRENGTH.index)
    if item_category:
        out["category_exact"] = sum(CATEGORY_LABEL[c] == gold[i] for i, c in item_category.items())
        out["category_total"] = len(item_category)
        out["category_by_item"] = {i: CATEGORY_LABEL[c] for i, c in sorted(item_category.items())}
        out["overclaim"] = sorted(i for i, c in item_category.items() if c == "illegal" and gold[i] != "违法/无效")
        out["underclaim"] = sorted(i for i in hits if gold[i] == "违法/无效" and item_category.get(i) != "illegal")
    grounding = record["result"].get("grounding") or {}
    out["dropped"] = grounding.get("cards_dropped", 0)
    out["missing_blocked"] = grounding.get("missing_blocked", [])
    out["retries"] = len(grounding.get("retry_reasons", []))
    illegal_hits = [i for i in hits if gold[i] == "违法/无效"]
    out["illegal_hits_with_law"] = sum(any(c.get("legal_basis") for c in by_item[i]) for i in illegal_hits)
    out["illegal_hits"] = len(illegal_hits)
    return out


def write_mapping(paths: list[Path], checklist: dict[int, dict], target: Path) -> None:
    mapping = {}
    for path in paths:
        record = json.loads(path.read_text(encoding="utf-8"))
        if "error" in record:
            continue
        mapping[path.name] = [{"card": i, "title": c.get("title"), "quote": (c.get("clause_text") or "")[:160],
                               "items": keyword_suggestions(c, checklist), "confirmed": False}
                              for i, c in enumerate(record["result"]["cards"])]
    target.write_text(json.dumps(mapping, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Mapping template written to {target}: check each card's items (use [] for findings outside the checklist), set confirmed to true, then rerun with --mapping.")


def report(scores: list[dict], gold: dict[int, str], checklist: dict[int, dict], unconfirmed: list[int]) -> str:
    name = lambda i: f"{i}. {checklist[i]['name_zh']}"
    lines = ["# 评测结果", ""]
    should = sorted(i for i, label in gold.items() if label in SHOULD_FLAG)
    lines.append(f"标准答案：{len(gold)} 项有标签，其中 {len(should)} 项应报出，"
                 f"{sum(1 for l in gold.values() if l in SHOULD_NOT)} 项不应报出。")
    if unconfirmed:
        lines.append(f"注意：{len(unconfirmed)} 项标签尚未人工核对，分数只能作参考。")
    ok = [s for s in scores if "error" not in s]
    for s in scores:
        lines += ["", f"## {s['run']}"]
        if "error" in s:
            lines.append(f"运行失败：{s['error']}")
            continue
        lines.append(f"- 卡片 {s['cards']} 张；召回 {len(s['hits'])}/{s['should']} = {s['recall']:.0%}；误报 {len(s['false_positives'])} 项")
        tiers = "，".join(f"{TIER_ZH[t]} {h}/{n}" for t, (h, n) in s["recall_by_tier"].items())
        lines.append(f"- 按频率层召回：{tiers}")
        if "category_total" in s:
            lines.append(f"- 类别一致 {s['category_exact']}/{s['category_total']}；说过头（判违法但答案不是）：{s['overclaim'] or '无'}；"
                         f"说轻了（答案违法但没判违法）：{s['underclaim'] or '无'}")
        lines.append(f"- 违法项命中且附法条：{s['illegal_hits_with_law']}/{s['illegal_hits']}")
        lines.append(f"- 没通过检查被去掉 {s['dropped']} 张；缺失卡被关键词拦下 {len(s['missing_blocked'])} 张；重试 {s['retries']} 次")
        if s["unmapped_cards"]:
            lines.append(f"- 未映射的卡片：{s['unmapped_cards']}（先用 --write-mapping 生成映射并确认）")
        if s["other_cards"]:
            lines.append(f"- 清单外的卡片：{s['other_cards']} 张")
        lines.append("- 漏报：" + ("；".join(name(i) for i in s["misses"]) or "无"))
        lines.append("- 误报：" + ("；".join(name(i) for i in s["false_positives"]) or "无"))
    if len(ok) > 1:
        recalls = [s["recall"] for s in ok]
        lines += ["", "## 多次运行汇总", f"- 平均召回 {mean(recalls):.0%}（最低 {min(recalls):.0%}，最高 {max(recalls):.0%}）"]
        counts = {i: sum(i in s["hits"] for s in ok) for i in should}
        unstable = [i for i, c in counts.items() if 0 < c < len(ok)]
        always_missed = [i for i, c in counts.items() if c == 0]
        lines.append("- 时有时无：" + ("；".join(f"{name(i)}（{counts[i]}/{len(ok)}）" for i in unstable) or "无"))
        lines.append("- 每次都漏：" + ("；".join(name(i) for i in always_missed) or "无"))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gold", type=Path, required=True)
    ap.add_argument("--runs", type=Path, nargs="+", required=True)
    ap.add_argument("--mapping", type=Path)
    ap.add_argument("--write-mapping", type=Path)
    ap.add_argument("--out", type=Path, help="also save the report as markdown")
    a = ap.parse_args()
    checklist = load_checklist()
    if a.write_mapping:
        return write_mapping(a.runs, checklist, a.write_mapping)
    gold, unconfirmed = load_gold(a.gold)
    mapping = json.loads(a.mapping.read_text(encoding="utf-8")) if a.mapping else None
    if mapping and any(not e.get("confirmed") for entries in mapping.values() for e in entries):
        print("警告：映射里还有 confirmed=false 的卡片，结果按建议映射计算。")
    scores = [score_run(json.loads(p.read_text(encoding="utf-8")), gold, checklist, mapping, p.name) for p in a.runs]
    text = report(scores, gold, checklist, unconfirmed)
    print(text)
    if a.out:
        a.out.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()

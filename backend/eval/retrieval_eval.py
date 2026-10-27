"""Retrieval hit rate of the /ask path, measured with the project's own chunker and embedding model.

For every labeled question: chunk the contract with chunker.chunk_text, embed the chunks with
embedder.embedding_fn into a throwaway Chroma collection, retrieve the top k chunks, and count a hit
when one of them covers at least half of the sentence that answers the question.

    cd backend
    python -m eval.retrieval_eval            # the configuration /ask uses today
    python -m eval.retrieval_eval --sweep    # also compare chunk sizes

Nothing is written to ./chroma_db. Results are saved to eval/results/.
"""
import argparse
import inspect
import json
import os
import pathlib
import sys
import time
from math import comb

HERE = pathlib.Path(__file__).resolve().parent
BACKEND = HERE.parent
os.chdir(BACKEND)                      # embedder.py opens ./chroma_db relative to the working directory
sys.path.insert(0, str(BACKEND))

from chunker import chunk_text         # noqa: E402  the production chunker

SWEEP = [(100, 10), (150, 15), (200, 20), (300, 30), (500, 50), (800, 80)]
KS = (1, 3, 5)
MIN_COVER = 0.5                        # a chunk must contain at least half of the answer sentence


# ---------------------------------------------------------------- data

def load_data():
    contracts = {p.stem: p.read_text(encoding="utf-8") for p in sorted((HERE / "contracts").glob("*.txt"))}
    questions = [json.loads(line) for line in (HERE / "questions.jsonl").read_text(encoding="utf-8").splitlines()
                 if line.strip()]
    for q in questions:
        text = contracts[q["contract"]]
        for a in q["answer"]:
            n = text.count(a)
            if n != 1:
                raise SystemExit(f"{q['id']}: answer sentence found {n} times in {q['contract']}: {a!r}")
        q["spans"] = [(text.index(a), text.index(a) + len(a)) for a in q["answer"]]
    return contracts, questions


# ---------------------------------------------------------------- scoring (pure functions, unit-tested)

def chunk_spans(text, chunks):
    """(start, end) of each chunk in the text, or None if the chunker rewrote the text."""
    spans, cursor = [], 0
    for c in chunks:
        i = text.find(c, cursor)
        if i < 0:
            return None
        spans.append((i, i + len(c)))
        cursor = i + 1
    return spans


def covers(chunk_span, answer_span, min_cover=MIN_COVER):
    inter = min(chunk_span[1], answer_span[1]) - max(chunk_span[0], answer_span[0])
    return inter >= min_cover * (answer_span[1] - answer_span[0])


def is_hit(chunk, chunk_span, question):
    if chunk_span is None:                                  # fall back to plain containment
        return any(a in chunk for a in question["answer"])
    return any(covers(chunk_span, s) for s in question["spans"])


def random_hit_rate(n_chunks, n_relevant, k):
    """Chance that k chunks drawn at random include at least one relevant chunk."""
    k = min(k, n_chunks)
    return 1 - comb(n_chunks - n_relevant, k) / comb(n_chunks, k)


# ---------------------------------------------------------------- model helpers

def production_embedding():
    import embedder
    fn = embedder.embedding_fn
    name = None
    for attr in ("model_name", "_model_name"):
        name = name or getattr(fn, attr, None)
    k = inspect.signature(embedder.search_chunks).parameters["n_results"].default
    return fn, name or "paraphrase-multilingual-MiniLM-L12-v2", k


def visible_fraction_fn(model_name):
    """Share of each chunk the embedding model actually reads (it truncates at max_seq_length tokens)."""
    try:
        from sentence_transformers import SentenceTransformer
        m = SentenceTransformer(model_name)
    except Exception as exc:  # noqa: BLE001
        print(f"(token truncation not measured: {exc})")
        return None, None
    limit = m.max_seq_length - 2                            # [CLS] and [SEP]

    def visible(chunk):
        enc = m.tokenizer(chunk, add_special_tokens=False, return_offsets_mapping=True)
        if len(enc["input_ids"]) <= limit:
            return 1.0
        return enc["offset_mapping"][limit - 1][1] / len(chunk)
    return visible, m.max_seq_length


# ---------------------------------------------------------------- evaluation

def chunked(text, size, overlap):
    try:
        return chunk_text(text, chunk_size=size, overlap=overlap)
    except TypeError:                                       # a chunker without these parameters
        return chunk_text(text)


def evaluate(contracts, questions, embed_fn, size, overlap, k_prod, shared=False, visible=None):
    import chromadb

    client = chromadb.EphemeralClient()
    tag = f"s{size}o{overlap}{'x' if shared else ''}_{int(time.time() * 1000) % 10**8}"
    chunks = {c: chunked(t, size, overlap) for c, t in contracts.items()}
    spans = {c: chunk_spans(contracts[c], chunks[c]) for c in contracts}

    cols = {}
    if shared:                                              # every contract in one collection, as embedder.py stores them
        col = client.create_collection(f"eval_{tag}_all", embedding_function=embed_fn)
        for c in contracts:
            col.add(documents=chunks[c], ids=[f"{c}::{i}" for i in range(len(chunks[c]))])
        cols = {c: col for c in contracts}
    else:
        for c in contracts:
            cols[c] = client.create_collection(f"eval_{tag}_{c}", embedding_function=embed_fn)
            cols[c].add(documents=chunks[c], ids=[f"{c}::{i}" for i in range(len(chunks[c]))])

    kmax = max(max(KS), k_prod)
    rows = []
    for q in questions:
        c = q["contract"]
        res = cols[c].query(query_texts=[q["question"]], n_results=min(kmax, cols[c].count()))
        ranked = []
        for rid in res["ids"][0]:
            src, i = rid.split("::")
            i = int(i)
            hit = src == c and is_hit(chunks[src][i], spans[src][i] if spans[src] else None, q)
            ranked.append({"contract": src, "chunk": i, "hit": hit, "head": chunks[src][i][:70].replace("\n", " ")})
        n = len(chunks[c])
        relevant = sum(is_hit(chunks[c][i], spans[c][i] if spans[c] else None, q) for i in range(n))
        first = next((r + 1 for r, x in enumerate(ranked) if x["hit"]), None)
        rows.append({"id": q["id"], "contract": c, "lang": q["lang"], "question": q["question"],
                     "answer": q["answer"], "rank": first, "n_chunks": n, "relevant_chunks": relevant,
                     "random": {k: random_hit_rate(n, relevant, k) for k in set(KS) | {k_prod}},
                     "foreign": sum(x["contract"] != c for x in ranked[:k_prod]), "top": ranked[:k_prod]})

    vis = None
    if visible:
        allchunks = [ch for c in contracts for ch in chunks[c]]
        vis = sum(map(visible, allchunks)) / len(allchunks)
    return summarize(rows, k_prod, size, overlap, shared, vis, {c: len(v) for c, v in chunks.items()})


def summarize(rows, k_prod, size, overlap, shared, vis, n_chunks):
    def rate(rs, k):
        return sum(r["rank"] is not None and r["rank"] <= k for r in rs) / len(rs)

    ks = sorted(set(KS) | {k_prod})
    out = {"chunk_size": size, "overlap": overlap, "shared_collection": shared, "questions": len(rows),
           "chunks_per_contract": n_chunks, "k_production": k_prod,
           "hit": {k: rate(rows, k) for k in ks},
           "random": {k: sum(r["random"][k] for r in rows) / len(rows) for k in ks},
           "mrr": sum(1 / r["rank"] for r in rows if r["rank"]) / len(rows),
           "visible_fraction": vis,
           "foreign_share": sum(r["foreign"] for r in rows) / (len(rows) * k_prod),
           "by_contract": {}, "by_lang": {}, "rows": rows}
    for key, field in (("by_contract", "contract"), ("by_lang", "lang")):
        for v in sorted({r[field] for r in rows}):
            rs = [r for r in rows if r[field] == v]
            out[key][v] = {"n": len(rs), "hit": {k: rate(rs, k) for k in ks}}
    return out


# ---------------------------------------------------------------- report

def pct(x):
    return "  n/a" if x is None else f"{100 * x:5.1f}%"


def report(main, shared, sweep, k):
    print(f"\n== /ask retrieval as configured today: chunk_size={main['chunk_size']}, overlap={main['overlap']}, "
          f"top {k} chunks, {main['questions']} questions")
    print(f"   chunks per contract: {main['chunks_per_contract']}")
    for kk in sorted(main["hit"]):
        print(f"   hit@{kk}: {pct(main['hit'][kk])}   (random chunks: {pct(main['random'][kk])})")
    print(f"   MRR: {main['mrr']:.3f}")
    if main["visible_fraction"] is not None:
        print(f"   share of each chunk the embedding model reads: {pct(main['visible_fraction'])}")
    print("   by contract: " + ", ".join(f"{c} {pct(v['hit'][k])} (n={v['n']})" for c, v in main["by_contract"].items()))
    print("   by question language: " + ", ".join(f"{c} {pct(v['hit'][k])} (n={v['n']})" for c, v in main["by_lang"].items()))
    if shared:
        print(f"\n== all three contracts in one collection (embedder.py stores every upload in 'contracts' and "
              f"search_chunks does not filter by document)")
        print(f"   hit@{k}: {pct(shared['hit'][k])}   retrieved chunks from the wrong contract: {pct(shared['foreign_share'])}")
    misses = [r for r in main["rows"] if not (r["rank"] and r["rank"] <= k)]
    if misses:
        print(f"\n== misses at top {k} ({len(misses)})")
        for r in misses:
            print(f"   {r['id']} [{r['lang']}] {r['question']}")
            print(f"      expected: {r['answer'][0]}")
            print(f"      got #1:   {r['top'][0]['head']}...")
    if sweep:
        print(f"\n== chunk size sweep (top {k}; context = characters sent to the LLM)")
        print("   size  overlap   hit@1   hit@3   hit@5   random@3  model reads  context")
        for s in sweep:
            print(f"   {s['chunk_size']:4d}  {s['overlap']:6d}  {pct(s['hit'][1])} {pct(s['hit'][3])} {pct(s['hit'][5])}"
                  f"    {pct(s['random'][3])}     {pct(s['visible_fraction'])}   {s['chunk_size'] * k:5d}")


def main():
    if hasattr(sys.stdout, "reconfigure"):  # Git Bash on Windows otherwise prints Chinese through GBK
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", action="store_true", help="also compare chunk sizes")
    ap.add_argument("--k", type=int, help="chunks retrieved per question (default: search_chunks' n_results)")
    args = ap.parse_args()

    contracts, questions = load_data()
    embed_fn, model_name, k_default = production_embedding()
    k = args.k or k_default
    visible, max_len = visible_fraction_fn(model_name)
    sig = inspect.signature(chunk_text).parameters
    size = sig["chunk_size"].default if "chunk_size" in sig else None
    overlap = sig["overlap"].default if "overlap" in sig else None
    print(f"model {model_name} (reads at most {max_len} tokens per chunk), "
          f"{len(contracts)} contracts, {len(questions)} questions")

    main_res = evaluate(contracts, questions, embed_fn, size, overlap, k, visible=visible)
    shared_res = evaluate(contracts, questions, embed_fn, size, overlap, k, shared=True)
    sweep = [evaluate(contracts, questions, embed_fn, s, o, k, visible=visible) for s, o in SWEEP] if args.sweep else []
    report(main_res, shared_res, sweep, k)

    out = HERE / "results"
    out.mkdir(exist_ok=True)
    path = out / f"retrieval_{time.strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps({"model": model_name, "max_seq_length": max_len, "k": k, "main": main_res,
                                "shared_collection": shared_res, "sweep": sweep},
                               ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nsaved {path.relative_to(BACKEND)}")


if __name__ == "__main__":
    main()

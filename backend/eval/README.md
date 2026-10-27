# Retrieval evaluation / 检索评测

Measures whether retrieval finds a labeled contract passage. It does not measure LLM answer correctness or legal accuracy.
衡量检索是否找到标注的合同原文，不衡量模型回答或法律判断是否正确。

```bash
cd backend
source venv/Scripts/activate
python -m pip install -r requirements-dev.txt
python -m pytest tests eval -q
python -m eval.retrieval_eval
python -m eval.retrieval_eval --sweep
```

After the embedding model has been cached, run offline with:

```bash
HF_HUB_OFFLINE=1 python -m eval.retrieval_eval
```

## Method

- Use production `chunker.chunk_text` and `embedder.get_embedding_function()` with `paraphrase-multilingual-MiniLM-L12-v2`.
- The main experiment puts all three contracts into one in-memory Chroma collection. It calls the production `store_chunks` and `search_chunks` functions, including the document metadata filter.
- The comparison experiment puts all contracts into another shared collection and queries without filtering, reproducing the old bug. It uses an evaluation-only query, not the repaired production search function.
- No persistent Chroma client is opened and no DeepSeek request is made. Evaluation collections are deleted afterward.
- Both `/ask` and the evaluator default to top-3. `--k` changes only the evaluation setting.
- A chunk is relevant if it covers at least half of any labeled answer span; hit@k requires at least one relevant chunk in the first k results.
- The random baseline is the exact probability of hitting at least one relevant chunk when sampling k chunks without replacement from the selected document. It is not a random baseline for the unfiltered mixed pool.
- Wrong-contract share counts returned top-k chunks whose source document differs from the question's document, divided by the number of returned top-k chunks.
- The model-visibility diagnostic estimates the fraction of chunk characters represented before the embedding model's token limit. Defaults remain 500 characters / 50 overlap; the optional sweep changes both size and overlap.

核心对照：相同合同、相同问题、相同切块与模型，只比较共享库检索时是否按文档过滤。

## Recorded result, 2026-10-27

See [the complete saved run](results/retrieval_20261027-150842.json).

| Shared collection | Hit@3 | Wrong-contract share |
| --- | --- | --- |
| With document filtering | 73.2% (41/56) | 0.0% |
| Without filtering, reproducing the old bug | 58.9% (33/56) | 43.5% |

Filtered random@3 is 30.9%. The [2026-10-19 result](results/retrieval_20261019-125133.json) remains unchanged; its main experiment used one collection per contract, rather than production document filtering.

## Data and limitations

`contracts/` contains three synthetic evaluation contracts: a Chinese residential lease, a Chinese employment contract, and an English residential lease for Urbana, IL. They are not actual signed contracts or authoritative legal texts.

`questions.jsonl` contains 56 questions with labeled answer passages. The English lease has 20 questions: ten in English and ten in Chinese. Answer passages are checked for an unambiguous occurrence in the specified contract.

Inputs are plain text, so retrieval evaluation excludes PDF extraction. Separate endpoint tests exercise real PDF parsing and real Chroma filters with deterministic test embeddings and mocked LLM responses. The dataset is small, and document filtering does not provide user authentication.

## Separate live structured-analysis check

The [2026-10-27 live analysis result](results/analysis_20261027-152735.json) covers the three synthetic contracts with three actual DeepSeek requests. It records 29/29 exact contract quotes and 43/43 references to injected law IDs. The Illinois sample has no statutory references, so its legal-ID rate is undefined, not 100%.

This is separate from the 56-question retrieval experiment. It does not establish legal correctness or completeness. See the [qualitative review](ANALYSIS_REVIEW_2026-10-27.md), including observed unsupported legal generalizations and the discrepancy between the original natural-language card-count request and schema limit.

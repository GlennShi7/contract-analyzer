# Retrieval evaluation / 检索评测

**October 30 update:** The [completion batch](COMPLETION_REVIEW_2026-10-30.md) now covers all sixteen short inputs twice plus the three full fixtures twice: 41 requests, 37 production-valid reports and one rejected generation row. All sixteen remain draft-labeled with no independent adjudication; selected evidence checks identify material failures. The four-tested/twelve-untested counts and lack-of-live-follow-up statements below describe the earlier October 29 batches. The offline validator now reports the October 30 batch separately.

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

## Current-prompt follow-up, 2026-10-29

The [new three-contract rerun and source-based review](ANALYSIS_REVIEW_2026-10-29.md) records three first-response successes, 36/36 exact quotes and 75/75 supplied-ID references. Three of six newly authorized requests were used; total usage was 45,731 tokens. [Validated reports and usage](results/analysis_20261029-195508-505323.json) retain analyzer, law-library and manifest hashes. The review identifies remaining unsupported contract facts, omitted exceptions and coverage gaps. These are repeated existing fixtures, not independent cases or a legal-accuracy benchmark. The October 27 and 28 results remain unchanged historical evidence.

## Offline reasoning-review materials

[Protocol and commands](REASONING_REVIEW.md), [16 paired draft inputs](reasoning_cases.json), and [seven source-anchored historical observations](reasoning_audit_2026-10-29.json) now support a local evidence-validation workflow: `python -m eval.reasoning_review`. It calls no provider and reports legal accuracy/recall as null. Four new inputs now have [live diagnostic observations](DIAGNOSTIC_REVIEW_2026-10-29.md), twelve remain untested, and none are independently adjudicated; the historical observations are separate from those cases. Source quotes, output locations and text fingerprints are checked to detect fabricated or stale evidence.

The eight-request diagnostic artifact includes a truncated response, a fabricated correction and a budget-blocked final follow-up case. Historical schema acceptance is not current quote-gate acceptance. The final server quote gate and original-input correction were verified against the saved responses offline, not with an extra billable call.

## Final enforced-quote live check

The [final implementation check](FINAL_ENFORCEMENT_REVIEW_2026-10-29.md) used the separate full-contract authorization's remaining three requests, bringing that allowance to 6/6 used. All three first responses passed the enforced quote gate: 36/36 exact quotations, 56/56 supplied-ID references, 44,850 tokens. Genuine quotes still accompanied factual/interpretation errors (including twelve months changed to twelve years). This provides no general legal-accuracy or recall score and does not establish a successful live correction path. Both authorization batches are exhausted.

## Additional local-only review

The [five final-report findings](final_reasoning_audit_2026-10-29.json) are now checked by `python -m eval.reasoning_review` as a separate audit. Contract-fact checks use actual contract excerpts rather than unnecessary statutory IDs. The latest prompt separates municipal guidance from Chinese/unknown profiles and housing topics from employment analysis; this was initially verified with captured mock requests; the October 30 batch above now adds live evidence for that snapshot. The final full-contract live artifact continues to identify the earlier 9843ce0 code snapshot. Both paid authorizations remain exhausted.

# Project status

Reviewed on 2026-10-29 against the actual implementation and saved results. This is a working prototype; implementation completion and model-quality acceptance are separate.

| Area | Status | Evidence / limits |
| --- | --- | --- |
| Repository, dependencies and public documentation | Implemented | Complete default branch, environment examples, direct dependency pins, license, replay screenshots and setup instructions |
| PDF ingestion and document identity | Implemented | Full SHA-256 IDs, temporary-file cleanup, upload/page/text bounds, persisted text, page separators |
| Document-scoped retrieval | Implemented and exercised | Production top-3 filter, repeat-upload replacement, 56-question controlled evaluation and real-container smoke checks |
| Structured risk reports and legal sources | Implemented; quality review open | JSON/schema checks, quote matching, legal-ID filtering, selected Chinese and Urbana/state/federal snapshots |
| Risk-card interface | Implemented | Region choice, score, risk labels, contract excerpts and expandable legal sources |
| Question history | Implemented | Per-question pending/error/answer states, session-only history, explicit clearing and document-switch cancellation; each API question remains independent |
| Repeatable runtime and checks | Implemented | Compose, backend tests, actual-browser checks, real CPU embeddings and offline retrieval after container recreation |
| Model output reliability | Minimum live rerun complete; broader acceptance open | Current prompt: three existing fixtures passed on their first responses, using 3/6 authorized requests; repeated and independent samples remain necessary |
| Legal support and missed-risk assessment | Acceptance open | Source spot-checks found interpretation errors; no systematic applicability/false-positive/recall assessment has been completed |

## Remaining acceptance work

1. Extend reliability assessment beyond the three successful current-prompt samples. The [October 29 rerun and review](backend/eval/ANALYSIS_REVIEW_2026-10-29.md) preserve validated reports, code/source hashes, request counts and token usage; failed-run diagnostics preserve rejected responses. Three successes do not establish general reliability.
2. Review legal applicability, explanation support, false positives and missing risks using independent cases and explicit review criteria. The six existing manual counterexamples are review material, not passed model tests. Quote matching and allowed-ID membership do not substitute for this assessment.

The engineering flow is demonstrable. Neither the stored risk scores nor structural citation rates should be presented as calibrated legal accuracy. There is no verified user-count claim.

## Deliberate implementation choices

- Analysis is triggered after explicit region confirmation rather than automatically on upload.
- The page retains question history; the backend still receives one independent question at a time.
- The demo uses a clearly labeled interactive replay and actual screenshots.
- Defaults remain 500 characters / 50 overlap / top-3 to preserve the recorded evaluation configuration.
- OCR, accounts, public multi-user deployment and broader legal coverage are future product extensions, not silently included in the completed prototype.

## Verification references

[Verified CI at c75114f](https://github.com/GlennShi7/contract-analyzer/actions/runs/40982456843), [latest CI](https://github.com/GlennShi7/contract-analyzer/actions/workflows/ci.yml), [current-prompt rerun and review](backend/eval/ANALYSIS_REVIEW_2026-10-29.md), [retrieval evidence](backend/eval/README.md), [live-analysis review](backend/eval/URBANA_ANALYSIS_REVIEW_2026-10-28.md), [failed follow-up and diagnostics](backend/eval/URBANA_REASONING_FOLLOWUP_2026-10-28.md), [manual reasoning cases](backend/eval/URBANA_REASONING_CASES.md), [deployment and real-model checks](DEPLOYMENT.md).

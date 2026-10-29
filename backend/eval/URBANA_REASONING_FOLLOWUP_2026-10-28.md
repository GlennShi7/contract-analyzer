# Urbana interpretation follow-up, 2026-10-28

This continues the [first Urbana live review](URBANA_ANALYSIS_REVIEW_2026-10-28.md). It does not replace its raw result or claim a legal-accuracy improvement.

## Changes

At code snapshot `bdaffdd`, the prompt distinguishes contract facts, unverified facts and conditional legal conclusions across titles, summaries, explanations and suggestions. It warns against equating a consent condition with an absolute prohibition, inferring excessive actual costs from a fixed fee, or describing prima facie evidence as the only permissible proof. Three municipal applicability notes preserve those distinctions and the low-value/storage-cost abandonment exception.

All 43 original source texts, text hashes and provenance fields were compared with the prior commit and were unchanged. Applicability notes are explanatory metadata, not official statutory text.

The server's `legal_scope` now explicitly states that municipal boundaries have not been verified and that a mailing address or region selection is not boundary confirmation. This server-generated scope remains present even if the model overclaims in its summary; it does not automatically detect or rewrite every false model claim.

Six [manual counterexamples](URBANA_REASONING_CASES.md) distinguish consent from prohibition, fixed fees from demonstrated excessive costs, negotiated repairs from a handwriting-only requirement, low-value disposal exceptions, and mailing addresses from boundary evidence. They are review cases, not expert-scored benchmarks or model-generation test results.

## Authorized live follow-up: no validated report

The user authorized at most two requests for the existing synthetic English lease plus selected public statutes. The first Urbana run used one. The follow-up therefore ran with:

```bash
python -m eval.analysis_eval --live --contracts lease_en --english-jurisdiction us_il_urbana --max-requests 1
```

Exactly **one additional request** was sent. The analyzer did not accept the first response and attempted its correction path; the evaluator's hard limit blocked the next request before the SDK call. The command exited with `Live verification failed after 1 request(s): RuntimeError, HTTP None; no metrics saved.`

Thus the two-request authorization was exhausted without exceeding it. No additional API request was made. There is no validated follow-up report, quote metric or legal-ID metric, and no evidence yet that the prompt changes improved generated reasoning.

The evaluator at that time did not preserve rejected response content or its finish reason. The exact initial rejection cause—such as truncation, missing content, invalid JSON or a schema mismatch—cannot be recovered from the recorded command output. Token usage for that follow-up was also not saved. This document is a manual execution record, not a reconstructed response artifact.

## Diagnostic fix and local checks

The evaluator now saves failed-run diagnostics separately as `analysis_failed_*.json`: request count/model/usage where available, response content and finish reasons, prior validated rows if any, a failure type, and `metrics: null`. Only synthetic fixture outputs are involved. Successful runs continue to save their validated metrics separately, and now include hashes of all three actual law-library files so edits to applicability notes are traceable too.

76 backend tests passed after the diagnostic change, with two upstream deprecation warnings. New mocked checks verify that a rejected response cannot trigger a second SDK call when the limit is one, that invalid JSON and truncated finish reasons are preserved in failure diagnostics, and that failures have no success metrics. No paid call was made to test diagnostic saving, and the lost response from the real follow-up was not recreated.

No frontend source code changed in this follow-up. Model explanation quality remains an open evaluation issue; future authorized checks should inspect structured-output failures as well as legal reasoning and should include counterexamples beyond the original long lease.

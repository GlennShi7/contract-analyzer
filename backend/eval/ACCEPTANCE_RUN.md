# Completion-check batch

This batch is **prepared, not authorized or executed**. Historical paid-call allowances are exhausted. A new explicit user approval is required before adding `--live`. Preparation, unit tests and CI make no model requests.

The plan contains the sixteen existing paired diagnostic inputs and three existing full synthetic contracts, each run twice with one frozen analyzer/source/model snapshot: **38 requested reports, at most 76 provider requests including corrections and failures**. The short cases use the Urbana profile; the full English lease uses Urbana and the two full Chinese contracts retain the Chinese profile. Only these synthetic texts and selected repository statute snapshots are sent. No private contract, entire Excel code export or private handoff is part of this batch.

## Prepare and inspect

From `backend`:

```bash
python -m eval.acceptance_eval --output /path/to/new-batch
```

Inspect `plan.json` before any approval. It contains the exact synthetic inputs, draft criteria/source anchors, model, repetition order, request cap and normalized-text code/source fingerprints. `ledger.json` records zero requests in prepare mode. The manifest is fixed; this CLI does not accept arbitrary private input files.

Only after approval of this exact batch:

```bash
python -m eval.acceptance_eval --output /path/to/new-batch --resume --live
```

The same command can continue an interrupted batch under the **same cumulative 76-request cap**. It cannot reset counters or silently replace an existing plan. Changed code, source, model or input fingerprints block resume. A process lock prevents concurrent execution. An abandoned lock fails closed; inspect the old process and durable ledger before manually removing a stale lock. Never create another batch directory to evade the authorized cap.

Every attempt is durably recorded before the SDK is called, including correction attempts and network failures. SDK automatic retries must be disabled. Failed responses retain finish reason, raw content, model/usage and request payload. Incomplete prior rows remain interrupted and are not regenerated on resume. A provider failure stops the batch with saved evidence; unused planned rows remain explicit. A schema/quote failure after the allowed correction is recorded and the next planned row can proceed within the cap.

## Review the evidence

- `ledger.json`: authoritative request/response evidence and schema-accepted reports. Schema-accepted does not mean legally correct.
- `comparison.json`: per-input repeat status, scores and card titles. Differences are visible; similarity does not establish legal correctness or general stability.
- `review-template.json`: generated, unreviewed seven-dimension matrix bound to the ledger fingerprint. **Copy it to a separate review file before filling it out**; the template is regenerated after live/resumed runs. Keep the original output and source evidence alongside every judgment.

Review contract facts, scope, conditions/exceptions, legal support, false positives, target-issue coverage and consistency across titles/summaries/explanations. Preserve failed/missing generations and unknown judgments. The two repetitions can expose variation, but are insufficient to prove stable performance. All short cases were designed after observed failures; they are not held-out inputs. The full contracts are also reused fixtures.

Apply the [reasoning review protocol](REASONING_REVIEW.md), including reviewer identity/role, exact output/source anchors, a second independent review and disagreement resolution before publishing legal-accuracy or recall numbers. The runner deliberately leaves those metrics null. It cannot supply an independent legal reviewer or establish current law from the historical source snapshots.

## Offline checks

```bash
python -m pytest tests eval -q
python -m eval.reasoning_review
```

Mock-client tests cover the no-client prepare path, all 19 inputs/two rounds, durable counts before sends, cumulative limits across resume, failed/correction requests, zero SDK retries, concurrent/stale locks, interrupted rows, changed-plan rejection, existing-file refusal and unreviewed worksheet labels.

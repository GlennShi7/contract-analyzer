# October 30 completion review

**Engineering flow implemented; model-quality gate not accepted.** The explicitly approved batch finished all 38 planned generation rows using **41 of at most 76 provider requests**. Thirty-seven reports passed production schema/quote validation; the first Chinese labor-contract generation failed after its allowed correction. The batch is finished, with 35 unused requests that are not permission for a different or changed-prompt batch.

This is a source-based engineering review by an AI coding assistant, **not independent legal adjudication**. The inputs reuse existing fixtures and post-error diagnostic drafts. No legal accuracy, false-positive rate, calibrated risk score or complete risk-recall result is claimed.

## Scope and reproducibility

- Sixteen existing short diagnostic inputs and three full synthetic contracts, two rounds with the same analyzer/source/model plan.
- Urbana/Illinois/federal profile for the English inputs; the existing Chinese profile for the two Chinese full contracts. No private contracts or entire Excel code export sent.
- Frozen plan fingerprint: `d3caaa8d25b3462b39348863a1e9067e3e6437c62a36fa4933a0fd534db30233`.
- Durable ledger fingerprint: `170d45fc295e4f6cf252acb59c632a126ea99d3c742e80bfc4acedb95a87430c`.
- No prompt changes between rounds. The server still enforces one correction, original-input restart, no SDK retries, and exact/conservative-whitespace quotation acceptance.

[Exact inputs and source/code fingerprints](results/completion_20261030/plan.json), [request payloads, raw responses, usage and reports](results/completion_20261030/ledger.json), [runtime versions](results/completion_20261030/environment.json), [mechanical integrity summary](results/completion_20261030/integrity.json).

## Mechanical results

All 41 provider responses were retained. The 37 accepted reports can be reconstructed offline from their raw responses with the frozen production prompt and settings; all **215 card quotations match exactly**. Their **400 references belong to the supplied law IDs**. Those facts do not establish whether the quote supports an explanation or whether a statute applies.

The three extra requests were corrections: two responses included a forbidden `summary_note` field and were corrected; both attempts at the first labor report changed the penalty recipient from the employer to the employee, so that report was rejected. The second labor generation passed. [Rejected-attempt diagnostics](results/completion_20261030/rejected-attempts.json) preserve the affected rows and fields. A regression test replays the bad labor responses and verifies rejection after exactly two calls.

Provider-reported usage including corrections: **816,332 prompt tokens + 60,390 completion tokens = 876,722 total tokens**. These are usage records, not a dollar-price estimate.

## Selected review findings

The [41 anchored observations](results/completion_20261030/selected-review.json) include 28 narrowly supported observations and **13 selected failures**. They are observations, sometimes multiple per report, not a denominator or a legal pass rate. Every record contains exact output evidence and relevant input/source anchors. Unreviewed dimensions in the [review template](results/completion_20261030/review-template.json) remain unreviewed.

Material failures include:

- A generic leasing declaration is reused as a quote for missing-information cards despite the explicit instruction to keep missing information in the summary. Exact quote matching does not catch relevance errors.
- Both estimated-deposit examples claim normal-wear protection is absent even though the quoted clause says damage must be beyond normal wear.
- A deposit-return explanation says the 45-day start event is unspecified although its own quote says after the tenant vacates.
- A receipts explanation omits the supplied estimated-cost/later-receipts alternative; a showing suggestion overgeneralizes the 24-hour notice rule despite the supplied conditional showing exception.
- An explanation conflates whole-unit abandonment with the separate post-termination property route. Both English full-contract titles associate a subletting fee with unapproved subletting even though the quoted fee is conditioned on approval.
- The second compliant-showing example acknowledges the stipulated periods but replaces explanation of the target notice exception with missing-term cards.

Positive target observations include the consent-versus-absolute-subletting distinction, unknown versus stipulated actual costs, handwriting as evidence rather than an exclusive form, low-value disposal exceptions, and silence versus an express interest waiver. These observations do not endorse every card in the same report.

## Repeat variation

Among the 18 inputs with two production-valid reports, **2 changed score and 14 changed card count**. For example, the outside-city case produced six cards in round one and none after correction in round two; the compliant-showing case produced five and ten. The latter also changed from explicitly recognizing the notice exception to omitting its effect. These finite repeated/post-error inputs expose variation; they do not prove general stability or estimate its population rate. [Per-input comparison](results/completion_20261030/comparison.json).

## Verify without paid requests

From `backend`:

```bash
python -m pytest tests eval -q
python -m eval.reasoning_review
python -m eval.acceptance_review eval/results/completion_20261030/ledger.json --review eval/results/completion_20261030/selected-review.json
```

The last command verifies the frozen snapshot, raw-response reconstruction and evidence locations. It creates no provider client. It requires the recorded code/source/model snapshot; after changing those, reproduce the matching snapshot instead of calling these historical outputs current. The [batch workflow](ACCEPTANCE_RUN.md) documents cumulative counting and resume behavior.

## Acceptance boundary

Repository/setup, document isolation, original-text persistence, risk-report and Q&A flows, English/Chinese UI, responsive presentation, duplicate/stale-request protections, rendering guards and reproducible engineering checks are implemented. Local backend verification now includes **154 tests**, including the new budget/provenance and rejected-recipient regressions.

The live-check and source-based review tasks are complete, but their outcome is negative for broader model-quality acceptance. Semantic explanation support, independent adjudication, unseen-case coverage and current-law verification remain unestablished. Existing known failures prevent calling this a reliable legal decision system. OCR, accounts, public multi-user hosting and wider law coverage remain future extensions to the original prototype scope.

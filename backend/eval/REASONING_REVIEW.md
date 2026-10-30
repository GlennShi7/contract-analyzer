# Reasoning review protocol and diagnostic cases

Prepared 2026-10-29. This is a local engineering review workflow, not legal advice, independent legal adjudication or a calibrated benchmark. It makes **no provider requests**. It does not establish the currency of the source snapshots.

## What is available

- [Sixteen diagnostic inputs](reasoning_cases.json): eight pairs contrasting subletting, actual-cost facts, repair elections, disposal exceptions, municipal boundaries, estimated deposit costs/receipts, silence versus an interest waiver, and showing access.
- [Seven selected observations on the saved English lease report](reasoning_audit_2026-10-29.json): one unsupported assertion, two omitted conditions/paths, three narrowly supported observations and one unassessed distinction. These findings are **not** results for the sixteen new inputs and do not form an exhaustive accuracy denominator.
- [Offline evidence validator](reasoning_review.py): checks complete pairs, unique IDs, source-text fingerprints and exact source quotes. It checks the reviewed report fingerprint, structured evidence locations, output quotes and any supplied contract excerpts. Paths cannot escape the repository.

Four of the sixteen diagnostic inputs now have [live observations](DIAGNOSTIC_REVIEW_2026-10-29.md); twelve remain untested. All sixteen still have **zero independently adjudicated labels**. The input manifest retains its initial empty run list; actual execution records are stored separately and merged by the offline validator. They were designed after observing failures, so they must not be called unseen or held-out cases. The case facts are synthetic stipulations, not real property verification. Except in the boundary pair, the inputs explicitly stipulate ordinary tenancy, municipal location, timing and no section 2 exclusion so that irrelevant missing-scope facts do not conceal the target distinction.

The older six-case [manual review note](URBANA_REASONING_CASES.md) remains historical material. The new set expands those distinctions and adds deposit/interest and showing-access contrasts; it does not retroactively score the old cases.

## Run without generation

```bash
cd backend
python -m eval.reasoning_review
python -m pytest tests eval -q
```

The validator outputs 16 draft cases, 8 pairs, 4 distinct model-tested cases, 12 untested cases, and 7 integrity-checked historical review records. It records 8 provider requests in the live artifact but itself makes 0 requests. The follow-up did not send the final interest-waiver case after exhausting its cap; seven schema-accepted historical reports do not mean seven legally correct outputs. `legal_accuracy` and `risk_recall` are `null`. The finding-count breakdown describes selected reviewer observations, not a pass rate. Valid evidence anchors do not automatically establish that a human conclusion is correct.

Source text SHA-256 values match the decoded statutory text, as in the production library. The report/contract fingerprints use UTF-8 text after universal-newline decoding so Git's CRLF/LF checkout changes do not break the review. Changes to substantive content still invalidate fingerprints. Law IDs refer to the complete local library sections; anchors are exact excerpts for review convenience, not replacements for the full provisions and their scope.

## Criteria for a future generated response

Retain the complete input, source-library/analyzer fingerprints, model/settings, raw response, finish reason, request count, usage and any validated report. Record every attempted provider request, including failed/correction requests. Do not mix the 56-question retrieval benchmark with these diagnostic inputs.

For each generated response, a reviewer fills this matrix. Use **supported / failed / unknown / not applicable**, with output and source evidence; do not convert unknown or not applicable into a pass.

| Dimension | Review question | Example of a failure |
| --- | --- | --- |
| Contract facts | Does the report preserve what is stated, unstated or stipulated? | Turning silence about interest into an express waiver |
| Scope and facts | Does the conclusion respect municipal location, tenancy exclusions, timing and other required facts? | Treating an Urbana mailing address as a completed boundary lookup |
| Conditions and exceptions | Does the explanation preserve conditions that change the conclusion? | Saying only valueless/perishable property can be immediately discarded |
| Legal support | Do the cited supplied provisions support the explanation, rather than merely having valid IDs? | Attaching a genuine ID to a different or overstated rule |
| False positive | Does a card assert an adverse/legal problem that the stipulated facts do not support? | Declaring a fixed fee necessarily above actual costs when costs are unknown |
| Expected-issue coverage | Does the output address the particular issue specified by this case? | Omitting the subletting distinction entirely |
| Uncertainty and consistency | Do title, summary, explanation and suggestion preserve the same limitations? | A categorical summary followed by a conditional explanation |

Quotation matching, schema validity and supplied-ID membership remain separate mechanical measurements. A quoted card can fail legal support. An empty card list is not an automatic success; examine the summary and expected issue. Absence of a dedicated card can mean a missed target issue, but do not call it complete legal-risk recall without an adjudicated expected-issue set.

Review both members of each pair. A generic caveat alone does not pass either case; the explanation must engage with its actual distinction. Summaries are included in the review even though the production quote metric covers card quotations only.

## Review record and publication gate

For each future case keep: case ID; output artifact path/fingerprint; seven dimension judgments; exact output/source evidence; reviewer identity/role; rationale; independent second review; disagreement and resolution. Until generation occurs, leave output and judgments unreviewed. The present seven historical observations have one source-based engineering review and no independent adjudication.

Before publishing accuracy, false-positive or recall numbers, establish an independently checked label set and define the denominator, missing-output treatment and disagreement policy. Report partial/failed runs explicitly. Multiple generations per case are needed to assess variability; one sample per case does not establish stability. Broader legal accuracy needs coverage beyond these post-error diagnostics and beyond the selected law library.

## Authorization boundary

The earlier six-request authorization for the **three existing full synthetic contracts** is now 6/6 used: the first three calls plus a [final-version rerun](FINAL_ENFORCEMENT_REVIEW_2026-10-29.md) of the same full inputs. A separate, subsequent eight-request authorization covered four short diagnostic inputs and selected public laws; it is now exhausted at 8/8, including a correction. Twelve diagnostic inputs were not sent. [The live review](DIAGNOSTIC_REVIEW_2026-10-29.md) distinguishes baseline and prompt-follow-up observations, the budget-blocked case, and the final quotation enforcement added afterward. The original statutory text was unchanged.

## Verification

New evidence-integrity tests reject missing contrast variants, duplicate cases, fabricated source/output quotes, stale fingerprints, invalid evidence pointers, out-of-repository paths, tampered statutory text and fictitious completed runs, and verify that CRLF checkouts preserve the review fingerprints. These tests validate the review tooling, not a legal judgment. Run the complete backend test suite with the command above; current CI evidence is linked from the repository status page.

## Final-report evidence and prompt isolation

A separate [five-finding audit](final_reasoning_audit_2026-10-29.json) now anchors the final full-contract report's duration, approval condition, judicial-procedure wording, deposit receipt path and Chinese-profile relevance issues. Contract-fact findings require the actual contract excerpt and fingerprint; legal-source findings require supplied statutory anchors; profile findings additionally check the selected profile in the saved report. The offline validator reports this audit separately from the earlier seven observations, without an accuracy denominator.

The global prompt previously included Urbana-specific checks even for Chinese or unknown regions, and housing topics even for employment contracts. The latest code isolates guidance by the selected region, available law library and contract type. Local mock-client checks verify that foreign guidance is absent in Chinese/unknown requests and retained in applicable Urbana requests. No statute, stored model response, quote gate, request cap or authorization balance changed. This prompt change has **no paid model follow-up** and does not automatically detect the other observed semantic errors.

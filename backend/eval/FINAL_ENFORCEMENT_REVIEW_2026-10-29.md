# Final quote-enforcement live check

Run date: 2026-10-29 America/Chicago (artifact UTC: 2026-10-30 01:28). Evaluated implementation: `9843ce09ce1a32b7e03944516648f0d07a8f723b`. [Saved validated reports and usage](results/analysis_20261029-202829-557149.json).

## Authorization accounting

Two separately authorized batches were kept separate:

| Authorization | Inputs | Actual use |
| --- | --- | --- |
| At most 6 requests | Three existing full synthetic contracts and selected public laws | 3 in the earlier run + **3 in this final run = 6/6** |
| At most 8 new requests | Four specified short diagnostic cases and selected public laws | **8/8**, as recorded in the [diagnostic review](DIAGNOSTIC_REVIEW_2026-10-29.md) |

All limits include corrections and failed requests. This final run used the three remaining requests from the full-contract authorization, not additional requests from the exhausted short-case batch. Both authorizations are now exhausted. No private contract or whole workbook was sent.

```bash
python -m eval.analysis_eval --live --contracts lease_zh labor_zh lease_en --english-jurisdiction us_il_urbana --max-requests 3
```

All three first responses passed current schema checks **and the new enforced quote gate**; no correction was needed. Thus the final code has live first-pass evidence, while its revised correction path has only local mocked/replayed regression evidence. Do not describe this run as a successful live correction test.

## Structural observations

| Input | Cards | Exact contract quotes | References belonging to supplied IDs | Requests |
| --- | --- | --- | --- | --- |
| lease_zh | 12 | 12/12 | 15/15 | 1 |
| labor_zh | 12 | 12/12 | 24/24 | 1 |
| lease_en, Urbana | 12 | 12/12 | 17/17 | 1 |
| Total | 36 | 36/36 | 56/56 | 3 |

Usage: 37,422 prompt + 7,428 completion = **44,850 tokens**. Model: `deepseek-flash`, temperature 0, non-thinking JSON mode, 4,096 output tokens, SDK retries disabled. Analyzer SHA-256: `7f63f46df272b01711bdb071e977cb4cf3802d0e0c4e4bc2681acc7ab5e26ad5`; source-manifest and actual law-library hashes are in the saved artifact.

These observations verify a narrow functional path on the existing fixtures. They do not establish independent accuracy, general stability, source currency, semantic support or risk recall.

## Remaining factual and interpretation errors

Selected source-based engineering observations, without independent legal adjudication:

- **English card 2 changes the duration.** The exact quotation says `an additional twelve-month term`; the explanation says `自动续约十二年`. The title says twelve months, so even the report contradicts itself. A correct quote does not validate the explanation's number or unit.
- **English card 9's title reverses the approval condition.** Its title says `未经批准转租的高额处理费`, while the quote begins `If Landlord approves a sublease`. The explanation more carefully distinguishes approval from prohibition and says actual costs remain unknown. The title must preserve the same facts and uncertainty.
- **English card 7 adds a judicial-procedure implication.** Its title/summary say `未经司法程序处置遗留物品`. The supplied §12.5-22(c) describes notice, storage, timing and immediate-disposal exceptions; it does not state a general court-order prerequisite for disposal. That additional proposition is not established by the cited source. Notice/storage and an independently required judicial procedure are different claims.
- **English card 10 still compresses deposit procedure.** It describes 30-day documentation/receipts and a 45-day return without preserving the estimated-cost-then-later-receipts path and all state timing conditions in the supplied text. The relevant exception remains a review issue even with genuine quotation and IDs.
- **Chinese lease summary asks about Urbana boundaries.** The selected region is `cn`; the report nevertheless lists missing Urbana-boundary information. US facts are not interchangeable with Chinese source applicability. This is a profile-relevance problem in the generated summary, not evidence that US statutes were injected: the selected law library and scope remained Chinese.
- **Coverage remains limited.** Every report reaches twelve cards; no independent expected-risk set or expert adjudication was supplied. This check cannot produce a legal-risk recall number. Not every explanation was adjudicated, and the listed issues are not an exhaustive error denominator.

The final quote gate blocks absent or changed quotations, including the fabricated correction saved in the short-case run. It does not compare every number in explanations to contract facts, validate titles or summaries, prove that real citations support conclusions, or decide legal applicability. The observed errors demonstrate those limits directly. The fingerprint identifies the evaluated 9843ce0 implementation. A subsequent local-only change isolates jurisdiction and contract-type guidance; it is not covered by this live result. The five selected issues are now also retained in a [machine-checkable evidence audit](final_reasoning_audit_2026-10-29.json).

## Verification and open gates

[CI for the evaluated implementation](https://github.com/GlennShi7/contract-analyzer/actions/runs/40984994806) passed: **124 backend tests**, actual-browser frontend checks, and real CPU-embedding retrieval with persistence across container recreation. The exact bad short-case responses are replayed offline to verify rejection and the two-attempt cap. New independent legal labels, the twelve untested diagnostic cases and broader repeated sampling remain open. Further billable tests require new authorization; neither prior allowance has remaining requests.

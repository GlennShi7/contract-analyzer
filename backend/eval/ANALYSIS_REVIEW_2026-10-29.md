# Current-prompt live check, 2026-10-29

Evaluated code: `c75114f7d1fe937fb59afe43188a680d25b6f289`. [Saved result](results/analysis_20261029-195508-505323.json). The artifact's UTC timestamp is 2026-10-30 00:55; the run occurred on October 29 in America/Chicago. This check uses the existing synthetic fixtures, not private or signed contracts.

## Method and request budget

The user explicitly authorized **at most six new billable requests**, including corrections, for the three existing synthetic contracts and selected public statutes. Previous authorizations are separate and were not reused. The command was:

```bash
python -m eval.analysis_eval --live --contracts lease_zh labor_zh lease_en --english-jurisdiction us_il_urbana --max-requests 6
```

Exactly **three requests** were sent, one per contract. All three first responses passed schema/type validation; no correction request was needed. Three authorized requests remain unused. There is no reason to consume the remaining allowance merely to reach its ceiling.

Model: `deepseek-flash`, temperature 0, non-thinking JSON mode, 4,096 output-token limit. This exercises the current prompt without changing it. The analyzer SHA-256 is `13b481d85e8c2328ee57d76acff81aa6000aa652c050e6ed26aac2532a4e81c4`; actual law-library and source-manifest hashes are saved alongside it. No source-currency recheck or new legal snapshot was performed for this run.

## Observed structural results

| Synthetic contract | Region | Cards | Exact quotes | Allowed IDs / emitted references | Requests | Prompt / completion tokens |
| --- | --- | --- | --- | --- | --- | --- |
| Chinese residential lease | cn | 12 | 12/12 | 23/23 | 1 | 6,561 / 2,767 |
| Chinese employment contract | cn | 12 | 12/12 | 31/31 | 1 | 6,835 / 2,602 |
| English residential lease | us_il_urbana | 12 | 12/12 | 21/21 | 1 | 23,687 / 3,279 |
| Total | — | 36 | 36/36 | 75/75 | 3 | 37,083 / 8,648 |

Total usage: **45,731 tokens**. Reference counts are occurrences before unknown-ID filtering, not distinct provisions; the English report cites 13 distinct provisions. The saved successful artifact retains validated reports and request usage, not an additional verbatim provider-response copy. Failed-run diagnostics retain rejected response content and finish reasons.

This completes the minimum three-fixture current-prompt functional rerun. Three first-pass successes do not estimate general structured-output reliability. Exact quotes and supplied-ID membership do not measure whether an explanation is supported, applicable or complete. The summary is not covered by the quote-verification metric.

## Source-based review observations

All 36 explanations and the three summaries were read; the issues below were checked against the relevant contract passages and supplied source snapshots. This is an engineering review without independent legal adjudication. It is not an accuracy score, an exhaustive audit or advice about a real tenancy.

### English lease: compare the previously recorded issues

| Prior issue | Observation in this run | Assessment limit |
| --- | --- | --- |
| Address treated as verified municipal location | Summary explicitly says the address and region selection do not establish city-boundary membership; cards preserve scope qualifications. | Better wording on this one fixture, not a boundary lookup. |
| Consent condition treated as an absolute subletting ban | No dedicated subletting card was emitted. | **Not assessed**. Omission cannot establish that the distinction is fixed. |
| Fixed subletting fee assumed to exceed costs | No subletting-fee card. Other fixed-fee cards explicitly request actual-cost facts. | No result for the original $200 subletting example. |
| Handwriting treated as the sole permissible repair agreement | Card 4 discusses knowing/intentional election, actual bargaining and factual uncertainty without demanding handwriting. | The original failure wording is absent in this sample; no independent repair counterexample was generated. |
| Low-value/storage-cost immediate-disposal exception omitted | Card 8 again says immediate disposal is **only** for valueless or perishable property. The injected §12.5-22(c), including its applicability note, also preserves reasonable belief that sale value is below storage cost. | **Repeated material omission**, despite the prompt and note. |
| Deposit-interest conditions conflated | No dedicated interest card. The summary now lists “放弃押金利息,” although the contract contains no interest-waiver language. | **Unsupported contract-fact assertion**. Silence cannot be quoted as an explicit waiver. |
| No entry-right card | Card 9 quotes the last-90-days showing provision and discusses the tenant-selected showing periods in §12.5-15(c). | This omission did not recur; this is not a measurement of overall recall. |

Additional issues:

- **Deposit documentation, card 5:** the explanation and suggested replacement compress §12.5-20(a) into receipts within 30 days or full return within 45 days. The supplied text allows an estimated-cost statement followed by paid receipts within 30 days of that statement. Omitting that path changes the procedural description. Distinguish damage deductions from other deductions as well.
- **Coverage at the cap:** all three reports use all 12 cards. English subletting and a dedicated interest analysis are absent. No federal provision is cited, though the summary mentions housing age and lead disclosure. Those mentions do not test federal-law application. Card selection remains incomplete and uncalibrated.
- **No controlled causal claim:** differences from October 28 could reflect prompt changes or generation variation. This is one new sample, not a controlled demonstration that the prompt fixed reasoning errors.

### Chinese fixtures

- **Lease, card 1:** it cites Civil Code Article 496 for a term not becoming part of the contract but does not state that the supplied Article 496 ties that remedy to failure of the notice/explanation duty causing the other party not to notice or understand the term. The explanation separately discusses unfair standard terms, but should preserve the distinct prerequisites of the cited remedies rather than merge them.
- **Lease, card 12:** the quoted registration clause agrees with the supplied registration provision; its explanation itself says so. It is principally a verification item. Including it among 12 risk cards does not establish an adverse clause and may displace another issue. The summary also asks about building unit count and age without connecting those facts to a particular injected Chinese provision; these are not interchangeable with the US profile's statutory thresholds.
- **Employment:** the report distinguishes a three-year term's six-month probation period from its separately stated 70% pay term, and identifies the synthetic overtime, insurance, training-penalty, noncompete and termination provisions. These are qualitative observations, not passed legal labels. In card 9, wages and economic-compensation timing need separate assessment; the cited provisions do not establish every timing conclusion. The selected library is not a complete statement of employment law.

## Remaining acceptance work

1. **Independent cases and review criteria:** use the [six existing counterexamples](URBANA_REASONING_CASES.md) as starting material, with both sides of each distinction and explicit applicability facts. They were not sent in this batch; this authorization covered only the three existing full contracts. Add positive/negative cases for deposit estimates/receipts and interest silence versus express waiver.
2. **Separate measurements:** annotate contract-fact support, statutory conditions/exceptions, supported conclusion, false positives and omitted expected issues. Mark unknown facts as unknown. Keep valid quotation, allowed IDs and schema success as separate columns. Do not infer missing-risk recall without an adjudicated expected-issue set.
3. **Review independence:** have source-based labels independently checked and resolve disagreements before publishing legal-accuracy or recall numbers. More repeated generations would be needed for a stability estimate; these three samples are insufficient.

No production prompt or law text was changed after seeing this run, and no further paid request was made. The old failed follow-up remains an unresolved historical failure with missing diagnostics; this successful run does not reconstruct its cause. The interactive demo remains labeled as a replay of the October 28 result, including its documented limitations, rather than being silently replaced with this new sample.

## Engineering verification

[CI run 40982456843](https://github.com/GlennShi7/contract-analyzer/actions/runs/40982456843) passed at the evaluated commit: 100 backend tests, frontend lint/build and actual-browser checks, plus real CPU embeddings and document-filtered retrieval after container recreation. These checks verify the implementation and runtime; they do not validate the model's legal conclusions.

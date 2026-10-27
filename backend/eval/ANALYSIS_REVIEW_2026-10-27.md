# Live structured-analysis review, 2026-10-27

## Run identity

- [Saved API result](results/analysis_20261027-152735.json), evaluated at `2026-10-27T20:27:35.995961+00:00`.
- Implementation at the time of the run: [`bb98433`](https://github.com/GlennShi7/contract-analyzer/commit/bb98433ee59dcc64b95aa75ef54dc605a5848856).
- Model returned by the API: `deepseek-flash`.
- Inputs: the existing synthetic Chinese lease, Chinese employment contract, and English Illinois lease. No private contract was used.
- Jurisdiction settings: `cn`, `cn`, and `unknown`, respectively.
- Three actual requests; one per contract; no correction retries.
- Each input's SHA-256, the law-source manifest's SHA-256, per-request token usage, and structured output are recorded in the saved JSON.

## Recorded checks

| Input | Cards | Exact quotes | References belonging to the injected law set |
| --- | --- | --- | --- |
| `lease_zh` | 10 | 10/10 | 22/22 |
| `labor_zh` | 11 | 11/11 | 21/21 |
| `lease_en` | 8 | 8/8 | 0 references; rate undefined |
| Total | 29 | 29/29 | 43/43 |

The counts are computed before unknown law IDs are removed. All returned quotes matched exactly; no whitespace normalization or fuzzy hint was needed in this run. The totals represent one small run, not a general reliability estimate.

Recorded usage: 13,234 prompt tokens and 5,879 completion tokens, 19,113 total. This is token usage, not a price calculation.

## Observed limitations

1. **A matching citation does not establish legal support.** A valid law ID proves only that an article was in the injected list. There is no independent legal-expert assessment, legal-correctness benchmark, or measurement of missed risks in this experiment.
2. **Unsupported jurisdiction still elicited legal generalizations.** The English sample correctly had no Chinese law references, but its explanations mentioned possible statutory landlord duties and a general principle about deposits covering actual losses. No applicable Illinois legal source was supplied to support those statements. The output must not be presented as verified local legal advice.
3. **Natural-language limits were not fully followed.** The run's prompt requested up to eight risks, while its schema allowed twelve. The Chinese outputs contained ten and eleven cards. Both passed the actual schema. After inspecting this run, the prompt and schema were unified on a shared twelve-card constant, with an over-limit regression check. That wording change was not re-tested through additional paid requests; the recorded outputs remain from the implementation linked above.
4. **Risk scores are not calibrated.** Scores of 9, 9, and 8 are model-generated hints. They are not probabilities, legal findings, or comparable benchmark labels.

The live run validates that the implemented JSON/schema/quote/ID pipeline can complete on these inputs. It does not establish that every explanation is legally correct or that every relevant risk is detected.

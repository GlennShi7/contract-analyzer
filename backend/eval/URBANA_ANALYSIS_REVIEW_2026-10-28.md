# Urbana lease profile: live analysis review, 2026-10-28

Code snapshot: `0a36f43`. Raw result: [analysis_20261028-161231.json](results/analysis_20261028-161231.json). The output is retained as returned, including the issues below.

## Method and result

The existing synthetic `lease_en.txt` was analyzed with explicit `us_il_urbana` jurisdiction and the 43-provision municipal/state/federal library. This was not a signed contract. User authorization capped this run at two billable requests including correction attempts; **one request was made, with no retry**. No original workbook or private contract was sent.

Model: `deepseek-flash`, non-thinking JSON mode, temperature 0. Usage: 23,326 prompt tokens, 2,881 completion tokens, 26,207 total. Source-manifest and analyzer-file hashes are in the saved result.

| Structural property | Result |
| --- | --- |
| Cards | 12 |
| Contract quotes matched | 12/12, all exact |
| References to supplied law IDs, before filtering | 18/18 |
| Distinct cited provisions | 11 |
| Correction attempts | 0 |

These checks establish exact quotation and allowed-ID membership, not legal applicability, accuracy, completeness or calibrated risk. The 2026-10-27 unknown-region English result remains a separate historical baseline; this single rerun is not a controlled accuracy benchmark.

## Qualitative observations

The model now connects concrete terms to supplied municipal sources: automatic renewal to §12.5-10, late-fee accumulation to its 5% rule and actual-cost exception, unconditional carpet-cleaning deduction to §12.5-20, and abandonment to §12.5-22. It separates the municipal deposit-interest rule from the state's 25-unit condition, and marks towing law as needing verification without inventing a legal ID. These observations are source spot-checks, not an expert validation of every conclusion.

Material limitations remain:

- **Subletting:** the third card calls a requirement for prior written consent a prohibition. Those are not automatically equivalent. Its $200 fee also needs actual-cost facts; a fixed number alone does not prove an excessive charge.
- **Maintenance agreement:** the fifth card describes specially negotiated written agreement too categorically. Section 12.5-18 requires a knowing and intentional, actually bargained choice; its separate handwritten paragraph is *prima facie evidence*, not stated as the sole permissible proof. A repair-call cost allocation also needs analysis beyond assuming it transfers every maintenance duty.
- **Property location:** the summary asserts that the supplied address is inside Urbana. No boundary lookup occurred. An explicit user region choice and an Urbana address are not independent verification of municipal boundaries.
- **Abandoned property:** the eleventh card summarizes immediate-disposal exceptions as valueless or perishable, omitting the separate low-value/storage-cost exception preserved in the source. Its wording should not replace the complete provision.
- **Deposit interest:** the eighth card's title focuses on unit count even though the municipal rule has separate conditions not dependent on the state 25-unit threshold. Missing interest language in a lease does not by itself establish failure to pay interest.
- **Incomplete coverage:** the model reached the 12-card limit and did not produce a dedicated entry-right card, despite relevant contract language and §12.5-15 being supplied. No labeled legal-risk recall dataset was used.
- **Federal scope:** no federal provision was cited in a card. The summary flags housing age for lead-disclosure review, but that is not a successful test of federal-law application. The library does not include comprehensive implementing regulations or all housing programs.

Unknown law IDs are filtered, but misleading explanations attached to a genuine ID can still pass. The raw output demonstrates that limitation rather than resolving it. No further paid request was used to tune this example.

## Local verification

73 backend tests passed (two upstream deprecation warnings). Frontend production build and lint passed. The actual React interface was exercised in isolated headless Edge against a local mock API: unknown default, Urbana selection and request body, official source expansion, government level and applicability, quote-match labels, 502 handling and removal of a stale report. These browser checks do not call DeepSeek or validate legal reasoning.

# Four diagnostic inputs: live observations and quote enforcement

Date: 2026-10-29, America/Chicago. [Saved requests, raw responses and reports](results/reasoning_20261029.json). These are post-error synthetic diagnostics, not held-out examples, independent legal labels or a general accuracy benchmark. No private contract or workbook was sent.

## Authorization and execution

The user separately authorized **at most eight new requests**, including corrections, for four specified short cases and the selected 43 public provisions: `belongings_a`, `belongings_b`, `interest_fact_a`, `interest_fact_b`. This did not reuse the earlier six-request authorization, which remains at 3/6 used.

Exactly **8 SDK requests** were sent. SDK automatic retries were disabled. A durable counter was written before each request; the counter blocked a ninth send. Usage totals 194,866 tokens. This is usage, not a monetary cost estimate. Requests 1–4 are the baseline, using the analyzer from `d8528c4`. The two added general prompt constraints were then evaluated with requests 5–8. The analyzer fingerprints for both rounds are recorded in the artifact. Model: `deepseek-flash`, non-thinking JSON mode, temperature 0, 4,096 output tokens.

| Request | Case | Outcome |
| --- | --- | --- |
| 1 | belongings_a | Schema accepted, 8 cards |
| 2 | belongings_b | Schema accepted, 9 cards |
| 3 | interest_fact_a | Schema accepted, 11 cards |
| 4 | interest_fact_b | Schema accepted, 12 cards |
| 5 | belongings_a, prompt follow-up | Schema accepted, 1 card |
| 6 | belongings_b, prompt follow-up | Schema accepted, 1 card |
| 7 | interest_fact_a, prompt follow-up | `finish_reason: length`, rejected |
| 8 | interest_fact_a, correction | Schema accepted by the then-current code, 12 cards, **only 5 quotes matched** |

There was **no follow-up request for interest_fact_b**. Its failed row says `BudgetExhausted`; this denotes a blocked attempt, not a ninth paid call. The original runner's `unrun_cases` bookkeeping missed it because a failed row existed. The published artifact corrects that one metadata list and explains the correction; request records, provider content and report objects are unchanged. The portable runner now derives this list from actual request records.

## What the outputs show

### Baseline: exact quotation did not establish support

All 40 baseline card quotations matched input text, and all 101 emitted references belonged to the injected ID set. Nevertheless, many missing-information cards quoted only `Landlord leases a dwelling to Tenant.` or another unrelated true excerpt. That text cannot substantiate a specific adverse maintenance, lead-disclosure, payment or other clause. Missing facts may deserve a summary check; attaching a genuine but irrelevant quotation creates a misleading risk card.

In `belongings_a`, the clause already limits disposal to a reasonable belief that sale value is $5 when storage costs $100. The baseline recites the low-value exception but still describes immediate disposal as being in obvious tension with the general notice rule. This confuses checking the reasonableness of real behavior with comparing the clause's conditions to the supplied exception. `belongings_b` supplies the opposite facts and a blanket disposal term; those inputs should not receive interchangeable conclusions.

In the interest pair, the baseline distinguishes absence of interest language from an express waiver. This is a limited observation on those short inputs; the earlier full-contract summary still contains its unsupported waiver assertion.

### Prompt follow-up: a narrow improvement and a serious failure

The prompt now explicitly permits empty cards, puts missing information only in the summary, forbids using unrelated generic text to pad cards, and distinguishes an exception-conditioned term from conduct whose facts remain unknown. Requests 5 and 6 each produce one relevant card. The `belongings_a` explanation expressly says the text does not itself show a conflict with the 30-day rule because the provision permits the stated low-value exception. The opposite case retains the general notice/storage issue. These observations do not establish a causal accuracy improvement: the prompts changed, the cases were selected after errors, and each output is one sample.

The interest-silence follow-up then generated a truncated response containing invented waiver clauses. Its correction returned syntactically valid JSON but again treated fabricated English clauses about confession of judgment, jury trial, repairs, interest and other rights as supplied contract text. The corrected summary says multiple waivers appear at the end, although the actual short input contains none. **Seven of its twelve card quotes do not match the input.** The five matching quotes do not validate their attached explanations. The historical artifact retains this bad result; its `validated` row status means the schema checks used at that time accepted it, not that it was legally or factually accepted.

Unlike the lost October 28 rejection, this new run retains the actual `length` finish reason and both responses. This diagnoses this new failure only; it does not reconstruct the older failure's cause.

## Production enforcement added after the live calls

The server now rejects a generated report if **any** card quote fails exact matching or conservative whitespace normalization. It permits at most one correction, then raises `AnalysisOutputError`; `/analyze` returns 502 rather than the fabricated report. Approximate/fuzzy similarity is insufficient. Empty cards remain valid with undefined quote rates.

Correction now starts again from the original system prompt and original contract input, with validation feedback. Rejected assistant text is not included as new conversational context. This prevents that path from presenting the model's own rejected text as apparent source material; it does not prove that a fresh response will be correct.

These enforcement changes were **not live-tested after the eight-request cap was reached**. A local regression replays the exact saved truncation and fabricated correction through the current analyzer with a mock client. The current code rejects both and stops after two calls. Another mocked check verifies successful correction from fabricated to genuine quotation, retaining the original input and omitting rejected assistant content. No ninth provider call was sent.

Strict quotation is still not semantic support. A model can attach an incorrect explanation to a real quotation, or invent facts in a summary. This guard does not automatically validate either case. The summary/quote distinction and legal applicability/recall gates remain open.

## Reproduction and remaining work

Offline only:

```bash
cd backend
python -m eval.reasoning_review
python -m pytest tests eval -q
python -m eval.diagnostic_eval --output eval/results/NEW_LEDGER.json
```

The last command is prepare-only by default: no client, ledger or billable request is created. Its optional `--live` and `--follow-up` modes require authorization for the actual inputs and enforce one cumulative eight-request ledger. Existing ledgers cannot be silently overwritten or restarted as new allowances. Failures and corrections count toward the cap.

Current local checks: **124 backend tests passed**. Billing tests block the ninth SDK call and count failed requests. Offline review reports four distinct cases tested, twelve not tested, seven historical schema-accepted reports, and the unrun last case in the follow-up. Legal accuracy and risk recall remain `null`.

Next acceptance work is still independent source-based adjudication, the remaining twelve diagnostic cases, repeatability beyond these selected cases, and a newly authorized live check of the final enforcement/correction path. This batch's eight-request allowance is exhausted; the earlier remaining three requests are restricted to the original full-contract inputs and were not repurposed. The demo remains the clearly labeled October 28 replay.

## Subsequent final-version check

The [final full-contract rerun](FINAL_ENFORCEMENT_REVIEW_2026-10-29.md) subsequently used the three remaining requests from the separate six-request full-contract allowance. All three first responses passed final quote enforcement, without a correction. This does not validate the revised correction path live or cure the interpretation errors. The full-contract authorization is now 6/6 used; the short-case authorization stays 8/8. No further paid call was made.

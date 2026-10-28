# Urbana, Illinois residential lease sources

`tenancy_us_il_urbana.json` contains **43 selected provisions: 21 municipal, 15 state, and 7 federal**, checked/extracted on 2026-10-28. `SOURCES_US_URBANA.json` records snapshots and exclusions. These are official texts with normalized paragraph whitespace, not LLM-generated paraphrases.

## Municipal snapshot

Text is extracted from the user-supplied official Municode export `UrbanaILCodeofOrdinancesEXPORT20260417.xlsx`, Sheet1 rows 566–620 (Chapter 12.5). The [city's official code page](https://www.urbanail.gov/city-clerk/page/city-code) identifies the publisher. Each selected provision records the official deep link, source cell, text checksum, export label and applicability notes. The workbook SHA-256 is in the manifest. The original workbook is not redistributed here.

The filename label `20260417` and workbook generation metadata `2026-10-28` do not independently prove that every later amendment has been codified. The rental chapter has no truncated cells. Elsewhere, the workbook has eight explicitly truncated cells; Chapter 5 contains an editorial pointer to separately available technical codes, not their full text. Those missing contents were not reconstructed or injected.

## State and federal sources

State sources are the official [Illinois General Assembly](https://www.ilga.gov/) texts of 765 ILCS 705, 710, 715, 721 and 742, plus 735 ILCS 5/9-213.1. Federal sources are the House Office of the Law Revision Counsel's [42 U.S.C. 3603](https://uscode.house.gov/us/usc/119-124/t42/s3603/), [3604](https://uscode.house.gov/us/usc/119-124/t42/s3604/), [3607](https://uscode.house.gov/us/usc/119-124/t42/s3607/), [4851b](https://uscode.house.gov/us/usc/119-124/t42/s4851b/) and [4852d](https://uscode.house.gov/us/usc/119-124/t42/s4852d/), current through Public Law 119-124 (2026-10-15) as displayed by the source. Relevant coverage and exemption text is retained.

Scope choices:

- The city profile requires a property **inside Urbana city limits**. An Urbana mailing address alone may not establish that. Champaign, Chicago and other municipalities are outside this profile.
- Current 765 ILCS 710/1 does not contain the old five-unit minimum. The 25-unit condition in 765 ILCS 715/1 concerns state deposit interest; municipal interest has its own conditions.
- Repealed 765 ILCS 720 is excluded; the current selected retaliation source is 765 ILCS 721.
- 765 ILCS 705/35, effective 2027-01-01, is excluded from this 2026-10-28 snapshot.
- Lead disclosure requires target-housing facts. The ten-day inspection opportunity in 42 U.S.C. 4852d(a)(1)(C) is for purchasers, not a universal tenant inspection period. Implementing regulations are not comprehensively included.
- Repair deductions, termination, and substitute housing require statutory facts and procedures. A maintenance concern does not by itself justify withholding rent.
- This profile does not cover U.S. employment contracts or comprehensively include all federal housing programs, military protections, judicial decisions, zoning rules or building standards.

## Loading and maintenance

Choose `us_il_urbana` explicitly; the default `unknown` injects no laws. Chinese and English keywords classify lease/labor text separately from jurisdiction. Recognizable conflicting location markers suppress injection; this is a keyword guard, not address or governing-law verification.

Each article has its official HTTPS URL, version, checked date, and text SHA-256. `load_laws` validates host allowlists, unique IDs and hashes, and excludes mismatched jurisdictions, unverified snapshots, future-effective and expired provisions using the explicit **2026-10-28 snapshot date**. Missing effective dates are not inferred. Refreshing requires checking official text/amendments and updating the snapshot and tests.

Prompts include government level, applicability and version metadata; expanded UI citations display these. A matched quote and an allowed legal ID do not establish that a provision applies or supports an analysis. Model output may still overstate a genuine provision.

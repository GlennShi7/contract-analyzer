# Contract Risk Analyzer frontend

React + Vite interface for PDF upload, extracted-text preview, structured risk cards, expandable official legal references, and questions about the uploaded contract.

The app keeps the returned `doc_id` and submits it to `/analyze`. Full contract text stays on the backend. Selecting or uploading another document clears the previous report.

The upload control rejects files larger than 20 MiB before sending a request and blocks duplicate pending uploads. The backend also caps PDFs at 200 pages and 100,000 extracted characters. HTML proxy errors, model/index 503 errors and incomplete upload responses produce readable messages. Page boundaries now preserve whitespace; upload earlier PDFs again to refresh their saved text and chunks.

The region selector defaults to other/unknown. Choose Chinese mainland for supported labor/lease contracts, or Urbana, Illinois for residential leases inside Urbana city limits. Other Illinois cities are outside this municipal profile. Expanded sources show government level and applicability conditions. Cards distinguish matched quotes from quotes requiring manual review; the risk score is a model-generated hint, not a legal determination.

From this directory:

```bash
npm ci
npm run dev
```

Start the FastAPI backend at `http://127.0.0.1:8000` first. Open the frontend at `http://localhost:5173`, which is the backend's configured CORS origin.

`VITE_API_URL` can override the API base URL; restart Vite after changing environment variables.

```bash
npm run build
npm run lint
```

After upload, use **问问这份合同** to submit questions. This page retains each question's pending, error or answer state and expandable source excerpts. Each API question is independent; prior Q&A is not sent as model conversation context. **清空本页问答** clears local history without deleting the contract or sending a request. Refreshing or selecting another file clears history; file selection also aborts the pending browser fetch. This does not guarantee cancellation of server-side generation or its cost.

Blank questions and duplicate pending submissions are blocked. Empty answers and mismatched document/source IDs become an error on that question, while earlier answers remain with their original questions. Retrieved excerpts are plain text and are not automatically verified evidence for the generated answer. Q&A does not inject the risk analysis's statutory profile.

Run the actual interface checks with a local mock API (no DeepSeek calls):

```bash
npm run check:qa-ui
```

The script uses headless Edge in a fresh temporary profile and discovers that browser's assigned debugging port, defaulting to the standard Windows Edge path. Set `EDGE_PATH` for another Chromium-compatible executable and `QA_UI_OUTPUT` to choose an artifact directory. Ports 18764 and 18765 must be available. It checks errors, source isolation, duplicate submission, file changes, aborted requests and mobile width, then saves desktop/mobile screenshots and a check record. Backend tests separately cover PDF parsing, retrieval isolation and empty/truncated model responses. See the [project README](../README.md) for setup and limitations.

## Interface and responsive checks

The UI uses a navy navigation area, a light reading workspace, consistent upload/analysis/question sections, and text-labeled risk levels. After import the upload control becomes compact. Extracted-text preview, legal scope, legal sources and question excerpts can be expanded separately. The two question suggestions fill and focus the field without submitting or making an API request. No new UI package, web font or image service is required.

The file picker has a native input and a visible label with keyboard focus treatment. Browser checks cover the empty workspace at 320/390/768/1200 CSS pixels, mobile Q&A with expanded sources, and a mobile risk report with an expanded law source. The checks preserve upload errors/limits, document isolation, independent question payloads, history clearing and pending-request cancellation. `check:qa-ui` also saves `workspace-empty-desktop.png` and `workspace-empty-mobile.png`; `check:demo-ui` saves `demo-mobile.png` in addition to the overview/question screenshots. The empty-workspace screenshots use the real React UI before any request to the local mock API; risk/question screenshots use the explicitly labeled historical replay.

## Interface language

The default interface is English. The header button switches between English and Chinese and stores the preference locally; if browser storage is blocked, the switch still works for the current page. The document language and page title follow the UI setting. Language changes preserve the current contract, region, report, questions and answers and do not send upload, analysis or question requests.

Only interface copy is localized: navigation, controls, hints, loading states, risk labels, source labels, fixed scope/disclaimer messages and known service errors. Generated summaries, card titles/explanations/suggestions, answers, user questions, filenames, extracted text and statutory text are not translated. Unrecognized non-English service errors get an English fallback with expandable original detail. This does not change backend prompts, payload schemas or model behavior.

The actual-browser checks cover English default and mobile layout, saved language preference across reloads, existing-error relocalization, unknown service details, and report/answer preservation without requests. The demo accepts English aliases for its two original preset questions; the returned answers and source objects remain identical.

Risk analysis blocks duplicate pending submissions and aborts its browser fetch when selecting another file. A response with a different document ID is rejected; failed or unreadable responses leave the Analyze button available for retry. Changing regions clears the previous report and updates the region hint. Aborting the browser fetch does not guarantee cancellation of server-side generation or billing. The local mock-browser check covers these transitions without model requests.

Before rendering an analysis, the UI checks the fields it displays: score, summary, scope, cards and source entries. Malformed fields, duplicate or unresolved source IDs, and non-HTTPS source links are rejected with a retryable error. The browser suite exercises sixteen malformed payloads, a valid zero-card report, and unchanged literal contract/source text. These checks protect rendering; they do not verify legal reasoning or establish that a source is authoritative. The backend retains its curated-source validation.

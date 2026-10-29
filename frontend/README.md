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

After upload, use **问问这份合同** to submit a question. The page shows the latest answer and expandable excerpts from the same document. Each question is independent; prior Q&A is not sent as conversation history. Selecting another file clears the question/result and aborts the pending browser fetch. This does not guarantee cancellation of server-side generation or its cost.

Blank questions and duplicate pending submissions are blocked. The interface rejects empty answers and mismatched document/source IDs, displays API errors, and removes stale results. Retrieved excerpts are displayed as plain text; they are not automatically verified evidence for the generated answer. Q&A does not inject the risk analysis's statutory profile.

Run the actual interface checks with a local mock API (no DeepSeek calls):

```bash
npm run check:qa-ui
```

The script uses headless Edge in a fresh temporary profile and discovers that browser's assigned debugging port, defaulting to the standard Windows Edge path. Set `EDGE_PATH` for another Chromium-compatible executable and `QA_UI_OUTPUT` to choose an artifact directory. Ports 18764 and 18765 must be available. It checks errors, source isolation, duplicate submission, file changes, aborted requests and mobile width, then saves desktop/mobile screenshots and a check record. Backend tests separately cover PDF parsing, retrieval isolation and empty/truncated model responses. See the [project README](../README.md) for setup and limitations.

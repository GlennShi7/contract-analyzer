# Contract Risk Analyzer frontend

React + Vite interface for PDF upload, extracted-text preview, and plain-text risk reports.

The app keeps the returned `doc_id` and submits it to `/analyze`. Full contract text stays on the backend. Selecting or uploading another document clears the previous report.

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

The `/ask` Q&A endpoint is currently available through the backend API documentation, without a frontend chat interface. See the [project README](../README.md) for setup and current limitations.

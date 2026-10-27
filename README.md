# Contract Risk Analyzer / 合同防踩坑工具

A full-stack prototype that extracts text from PDF contracts, generates plain-language risk reports with DeepSeek, and supports semantic clause Q&A through a FastAPI endpoint.

Built to help people understand unfavorable terms in rental and employment contracts before signing, and find relevant contract clauses when questions arise afterward.

## Implemented

- React frontend: upload a PDF, preview extracted text, and request a text risk report.
- FastAPI backend: PDF extraction with pdfplumber and whole-document analysis through the DeepSeek API.
- Hand-written RAG: overlapping character chunks, multilingual MiniLM embeddings, persistent ChromaDB, and document-filtered top-3 retrieval.
- Stable SHA-256 document IDs, server-side text persistence, repeat-upload replacement, and source excerpts in Q&A responses.
- Retrieval evaluation: 56 labeled questions across three synthetic contracts, including Chinese questions about an English lease.
- API credentials loaded from a local `.env` file.

The Q&A frontend, injected legal sources, and structured risk cards are not implemented yet.

## Architecture

```text
PDF -> /upload -> SHA-256 document ID + pdfplumber text extraction
              -> full text saved in backend/data/{doc_id}.txt
              -> 500-character chunks, 50-character overlap
              -> multilingual embeddings + doc_id metadata -> ChromaDB
              -> doc_id, filename, preview, n_chunks -> frontend

doc_id            -> /analyze -> load full text -> DeepSeek -> text report
doc_id + question -> /ask -> retrieve up to 3 chunks from this document
                         -> excerpts + question -> DeepSeek -> answer + sources
```

The frontend retains the document ID instead of receiving and resubmitting the full text. `/analyze` loads the stored text; `/ask` filters on the document ID. The embedding model runs locally; generation uses the DeepSeek API.

Document IDs use the complete SHA-256 hash of the uploaded PDF bytes. Renaming the same file preserves its ID; different contents with the same filename receive different IDs. Re-uploading replaces its indexed chunks and removes stale chunks. Local data is excluded from Git. PDFs uploaded before this change need to be uploaded again to create the stored text and document metadata.

## Run locally

The existing backend environment uses Python 3.14.5. The existing frontend environment uses Node.js 26.5.1 and npm 11.17.0. These record the development environment, rather than a compatibility guarantee for every platform.

Commands below use Windows Git Bash. The first embedding request may download model weights.

```bash
git clone https://github.com/GlennShi7/contract-analyzer.git
cd contract-analyzer/backend
python -m venv venv
source venv/Scripts/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Set `DEEPSEEK_API_KEY` in `backend/.env`, then start the backend:

```bash
uvicorn main:app --reload
```

Open [API documentation](http://127.0.0.1:8000/docs). In a second Git Bash terminal, from the repository root:

```bash
cd frontend
npm ci
npm run dev
```

Open [the frontend](http://localhost:5173). Select a text-based PDF, click upload, then click analyze. The frontend defaults to `http://127.0.0.1:8000`; set `VITE_API_URL` to override it. The backend currently allows the frontend CORS origin `http://localhost:5173`.

## API

| Endpoint | Request | Response |
| --- | --- | --- |
| `GET /hello` | None | Startup message |
| `POST /upload` | Multipart field `file` containing a PDF | `doc_id`, `filename`, `preview`, `n_chunks` |
| `POST /analyze` | `{"doc_id": "<64-character lowercase SHA-256>"}` | `doc_id`, `result` (plain-text report) |
| `POST /ask` | `{"doc_id": "<SHA-256>", "question": "When is the deposit returned?"}` | `doc_id`, `answer`, `sources` |

The Q&A endpoint can be tried through `/docs`; it is not connected to the React interface yet.

Each source has `doc_id`, a zero-based `chunk` index, and the retrieved `text`. Invalid or textless PDFs return 400; unknown document IDs return 404; a missing index returns 409; malformed request fields return 422; DeepSeek request failures return 502. An unconfigured API key returns 503 when generation is requested.

## Retrieval evaluation

The [2026-10-27 run](backend/eval/results/retrieval_20261027-150842.json) compares document-filtered production retrieval against an unfiltered reproduction of the original bug. Both experiments use the same 56 questions and 500-character chunks with 50-character overlap:

| Experiment | Hit@3 | Random baseline@3 | Retrieved chunks from other contracts |
| --- | --- | --- | --- |
| Shared collection, with document filter | 73.2% (41/56 questions) | 30.9% within the selected document | 0.0% |
| Shared collection, without filtering (old bug) | 58.9% (33/56 questions) | Not reported for the mixed pool | 43.5% |

A hit means at least one retrieved chunk covers half of a labeled answer span. This measures retrieval, not final answer correctness or risk-detection accuracy. The filtered experiment calls the production `store_chunks` and `search_chunks` functions with an in-memory collection. `/ask` now also retrieves top-3. No DeepSeek API call is part of this evaluation.

The [original 2026-10-19 run](backend/eval/results/retrieval_20261019-125133.json) is retained for comparison. See [evaluation methodology and commands](backend/eval/README.md).

```bash
cd backend
source venv/Scripts/activate
python -m pip install -r requirements-dev.txt
python -m pytest tests eval -q
python -m eval.retrieval_eval
# Optional: python -m eval.retrieval_eval --sweep
```

## Limitations

- Document filtering is not user authentication or access control. The prototype has no accounts; use synthetic documents for development.
- Scanned PDFs require OCR, which is not implemented.
- Reports are free text, without injected statutes or verified legal citations.
- The evaluation set is small and synthetic; it excludes PDF extraction and LLM generation quality.

This is a development prototype, not legal advice.

## License

[MIT](LICENSE)

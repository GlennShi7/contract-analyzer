# Contract Risk Analyzer / 合同防踩坑工具

A full-stack prototype that extracts text from PDF contracts, generates plain-language risk reports with DeepSeek, and supports semantic clause Q&A through a FastAPI endpoint.

Built to help people understand unfavorable terms in rental and employment contracts before signing, and find relevant contract clauses when questions arise afterward.

## Implemented

- React frontend: upload a PDF, preview extracted text, and request a text risk report.
- FastAPI backend: PDF extraction with pdfplumber and whole-document analysis through the DeepSeek API.
- Hand-written RAG: overlapping character chunks, multilingual MiniLM embeddings, persistent ChromaDB, and a backend `/ask` endpoint.
- Retrieval evaluation: 56 labeled questions across three synthetic contracts, including Chinese questions about an English lease.
- API credentials loaded from a local `.env` file.

The Q&A frontend, injected legal sources, structured risk cards, and per-document retrieval filtering are not implemented yet.

## Architecture

```text
PDF -> /upload -> pdfplumber -> extracted text -> frontend
                            -> 500-character chunks, 50-character overlap
                            -> multilingual embeddings -> persistent ChromaDB

Frontend text -> /analyze -> full text + prompt -> DeepSeek -> text report
Question     -> /ask     -> retrieve 2 chunks + question -> DeepSeek -> answer
```

`/analyze` uses the full text submitted by the frontend. `/ask` retrieves contract excerpts. The embedding model runs locally; generation uses the DeepSeek API.

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

Open [the frontend](http://localhost:5173). Select a text-based PDF, click upload, then click analyze. The frontend currently expects the backend at `http://127.0.0.1:8000`.

## API

| Endpoint | Request | Response |
| --- | --- | --- |
| `GET /hello` | None | Startup message |
| `POST /upload` | Multipart field `file` containing a PDF | `filename`, `preview`, `text` |
| `POST /analyze` | `{"text": "contract text"}` | `{"result": "plain-text report"}` |
| `POST /ask` | `{"question": "When is the deposit returned?"}` | `{"answer": "..."}` or `{"error": "..."}` |

The Q&A endpoint can be tried through `/docs`; it is not connected to the React interface yet.

## Retrieval evaluation

The [saved run](backend/eval/results/retrieval_20261019-125133.json) records the following results for 500-character chunks with 50-character overlap:

| Experiment | Hit@3 | Random baseline@3 | Retrieved chunks from other contracts |
| --- | --- | --- | --- |
| Each contract indexed separately | 73.2% (41/56 questions) | 30.9% | 0% by construction |
| All three contracts in one collection, without filtering | 58.9% | Not reported for the mixed pool | 43.5% |

A hit means at least one retrieved chunk covers half of a labeled answer span. This measures retrieval, not final answer correctness or risk-detection accuracy. The main result uses isolated evaluation collections; it is not an end-to-end measurement of `/ask`. The evaluator defaults to top-3, while the current `/ask` endpoint explicitly retrieves two chunks.

The evaluation exposed missing document isolation in the application's shared collection. This is a known issue awaiting a document-ID filter. See [evaluation methodology and commands](backend/eval/README.md).

```bash
cd backend
source venv/Scripts/activate
python -m pip install -r requirements-dev.txt
python -m pytest eval -q
python -m eval.retrieval_eval
# Optional: python -m eval.retrieval_eval --sweep
```

## Limitations

- Retrieval currently searches all uploaded contracts together. Use synthetic documents for development; document isolation is required before multi-user use.
- Scanned PDFs require OCR, which is not implemented.
- Reports are free text, without injected statutes or verified legal citations.
- The evaluation set is small and synthetic; it excludes PDF extraction and LLM generation quality.

This is a development prototype, not legal advice.

## License

[MIT](LICENSE)

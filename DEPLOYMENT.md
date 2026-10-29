# Run the local container demo

This runs the frontend and backend on one machine with Docker Compose. It does not publish a public website. The HTTP port binds only to `127.0.0.1`; the prototype has no accounts or per-user access control.

## Start

Install Docker with a running Linux container engine. From a fresh repository checkout:

```bash
cp backend/.env.example backend/.env
# Edit backend/.env and set DEEPSEEK_API_KEY for analysis and Q&A.
docker compose up --build -d --wait
```

If `backend/.env` already exists, keep it instead of copying over it. A blank API key permits startup, documentation and parsing validation; generation returns 503 until configured.

Open [the app](http://localhost:8080) or [API documentation](http://localhost:8080/api/docs). The frontend calls `/api`; Nginx forwards those requests to the backend. Uvicorn's `/api` root path makes the OpenAPI schema and documentation work through the same proxy. Native Vite development still uses its existing API URL and port 5173.

The first build installs CPU-only PyTorch and the application dependencies. The first valid PDF upload may download the multilingual embedding model. Health checks do not download weights or call DeepSeek; a healthy process does not mean that the model is cached or credentials have been validated. Generation requests remain billable when an API key is configured.

The proxy accepts request bodies up to 20 MiB and permits up to 180 seconds between backend response reads. This does not add a native-backend upload size limit. The existing textless/scanned-PDF limitation remains.

## Persisted data

Compose uses named volumes for extracted contract text, the Chroma index and the Hugging Face model cache. It does not mount the host's existing backend database or contract files. Containers run the backend as a non-root user. Runtime credentials come from `backend/.env`; Docker build contexts use allowlists and do not include that file, local databases, virtual environments or private handoffs.

```bash
docker compose ps
docker compose logs --tail 100
docker compose down
```

`down` stops and removes containers while retaining the named volumes. Do not add `--volumes` unless you intend to delete the demo's contract text, index and cached models. API-key changes require recreating the backend container, for example by running `docker compose up -d --force-recreate backend frontend`.

## Checks without paid calls

```bash
docker compose config --quiet
python scripts/smoke_stack.py
```

Use `config --quiet` to validate configuration without printing resolved environment variables. The smoke check covers the served app, proxy, health, API schema/docs prefix, invalid request validation and invalid PDF parsing. It deliberately avoids valid-document generation and model downloads. Separate backend tests exercise document isolation with deterministic test embeddings and mocked model responses.

## GitHub Actions

The CI workflow runs on pushes to `master`, pull requests and manual dispatch. Its jobs are:

- Ubuntu / Python 3.13: install the CPU dependency profile and run backend tests with model downloads disabled.
- Windows / Node 24: clean npm installation, lint, production build and the actual Q&A browser checks in isolated Edge with a local mock API.
- Ubuntu / Docker Compose: build both runtime images, wait for backend health, start Nginx and run the HTTP smoke check with a blank API key.

No DeepSeek secret is supplied, and the live-analysis evaluator is never run by CI. GitHub Actions are pinned to verified commits. Node/Python image minor versions and direct Python dependencies are specified; this is not a complete lock of all transitive Python dependencies or image digests.

Implementation references: [Compose readiness conditions](https://docs.docker.com/compose/how-tos/startup-order/), [FastAPI behind a proxy](https://fastapi.tiangolo.com/advanced/behind-a-proxy/), [official CPU PyTorch wheels](https://download.pytorch.org/whl/cpu/torch/).

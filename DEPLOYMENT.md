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

Individual PDFs are limited to **20 MiB, 200 pages and 100,000 extracted characters**, including in native development. The proxy allows 21 MiB per request to leave room for multipart framing around a 20 MiB file, and permits up to 180 seconds between backend response reads. The native handler checks the file before copying when its size is known, and counts bytes during copying as a fallback; multipart parsing itself occurs before that handler. Page/text limits are checked during PDF extraction. Oversized input returns 413; password-protected PDFs need unlocking, and scanned/textless PDFs remain unsupported.

Model initialization/index errors and unavailable storage return readable 503 responses. Initial model download still requires a usable network connection; complete caches support later offline operation. The client does not automatically retry uploads. If text saving fails after indexing, a manual re-upload replaces the same document's chunks rather than duplicating them.

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

For the real embedding path, run the following from the repository root:

```bash
python scripts/smoke_embeddings.py --exclusive --state embedding-smoke.json
docker compose up -d --force-recreate --wait --wait-timeout 120
python scripts/smoke_embeddings.py --exclusive --state embedding-smoke.json --verify-only
```

The first command uploads the committed synthetic PDF, repeats it under another filename, and uploads a second byte variant with identical parsed text. It checks full-file IDs, exact stored chunks, actual 384-dimensional CPU embeddings, document-filtered top-3 results and the existing labeled query `el01`. Model weights may download from Hugging Face during initial upload. This adds two synthetic documents to the current stack's volumes; it does not read other documents or call `/ask`, `/analyze` or an LLM provider, even if an API key is configured.

The second command recreates the demo containers while retaining named volumes. The final command makes no upload: it reads both saved documents and the vector index inside the new backend container, with `HF_HUB_OFFLINE=1`, and requires the same text hashes and retrieval results using the cached model. Its JSON state records runtime package versions, the model cache revision when available, chunk IDs and before/after results. This is a smoke assertion for one fixed question, not a new retrieval benchmark or legal-accuracy score. The previously recorded 56-question retrieval evaluation remains separate.

## GitHub Actions

The CI workflow runs on pushes to `master`, pull requests and manual dispatch. Its jobs are:

- Ubuntu / Python 3.13: install the CPU dependency profile and run backend tests with model downloads disabled.
- Windows / Node 24: clean npm installation, lint, production build and the actual Q&A browser checks in isolated Edge with a local mock API.
- Ubuntu / Docker Compose: build both runtime images, wait for backend health, start Nginx, run the HTTP smoke check, then test real synthetic-PDF upload/embeddings and verify persisted retrieval after container recreation. The API key remains blank.

No DeepSeek secret is supplied, and the live-analysis evaluator is never run by CI. GitHub Actions are pinned to verified commits. Node/Python image minor versions and direct Python dependencies are specified; this is not a complete lock of all transitive Python dependencies or image digests.

Implementation references: [Compose readiness conditions](https://docs.docker.com/compose/how-tos/startup-order/), [FastAPI behind a proxy](https://fastapi.tiangolo.com/advanced/behind-a-proxy/), [official CPU PyTorch wheels](https://download.pytorch.org/whl/cpu/torch/).

## Exclusive storage inspection

The real-embedding smoke check requires `--exclusive` and is intended for an **idle test stack**. It stops the backend, opens the existing volumes in a disposable one-off backend container, then restores the backend in a `finally` path, including on failed inspection. Do not run it against an active service. It does not change the production API, delete volumes, weaken vector/text equality, or call a model provider.

The old `docker compose exec ... python` inspection opened a second `PersistentClient` while the application held the same persistence directory. [Upstream contributor guidance](https://github.com/chroma-core/chroma/issues/3769) warns against assuming consistent shared-directory views across separate client processes. The inspection now has one storage owner at a time. CI checks three independent offline reopens after recreation, retaining exact vector fingerprints, source isolation, the fixed top-3 hit and full before/after equality. Failure output also retains partial observations from the inspection subprocess. This removes an unsupported test topology; it is not a claim of general retrieval determinism or an independently reproduced explanation for every historical failure.

# Local replay demo

This demo runs the actual React interface against a local Node fixture server. It requires no Python backend, Docker, embedding-model download or API key after installing frontend dependencies.

```bash
cd frontend
npm ci
npm run demo
```

Open [the replay](http://127.0.0.1:5174). Download the synthetic PDF from the visible banner, select that file, and click upload. Choose **美国 · Urbana, Illinois** and analyze. Ask exactly **押金多久退还？** or **会自动续租吗？** to try the two scripted answers. Ctrl+C stops the demo.

| | Replay (`npm run demo`) | Normal app / Compose |
| --- | --- | --- |
| Accepted document | Only the committed synthetic PDF, verified by SHA-256; renaming it is allowed | Uploaded text-based PDFs |
| Upload behavior | Verifies the fixture and returns its saved metadata | Parses the PDF, saves text, chunks and embeds it |
| Risk report | Unmodified English result from `analysis_20261028-161231.json` | New DeepSeek structured analysis |
| Questions | Two handwritten preset answers using exact chunks of the original TXT fixture | Actual document-filtered retrieval plus DeepSeek generation |
| Model/API calls | None | Billable generation when configured |

The replay is a UI walkthrough, not evidence of live parsing, retrieval, legal correctness or improved reasoning. Its 24-chunk metadata and Q&A excerpts come from the original TXT fixture, not a new parse of the PDF. PDF headers, line breaks and footers can change chunk boundaries in normal mode. The stored risk result contains known interpretation errors, including subletting/maintenance explanations and an unsupported city-boundary assertion; see the [original review](../backend/eval/URBANA_ANALYSIS_REVIEW_2026-10-28.md). The banner labels these limitations. Unsupported questions and other PDFs are rejected rather than routed to a real model.

The three-page PDF reproduces all 27 numbered clauses from the existing synthetic English evaluation lease. It is not a signed agreement or a recommended lease. Text extraction and all 12 historical contract quotations are checked against the generated PDF. No user contract or personal legal document is included.

## Reproduce checks and screenshots

```bash
cd frontend
npm run test:demo
npm run check:demo-ui
```

The first command tests fixture identity, unchanged analysis replay, region validation, source IDs and unsupported requests. The second uses isolated headless Edge to exercise the actual interface and capture the overview and scripted Q&A. Set `EDGE_PATH` if needed and `DEMO_UI_OUTPUT` to choose the screenshot directory. It never calls DeepSeek. The screenshots in the project README are captured from this mode; they are not fresh model outputs.

## Rebuild the committed fixture

From the repository root, using Python with the optional PDF-generation dependency:

```bash
python -m pip install -r scripts/requirements-demo.txt
python scripts/make_demo_fixture.py
```

The script reads the existing TXT fixture, uses the production chunker for saved excerpt boundaries, and rebuilds `demo/lease_en.pdf` plus `demo/fixture.json`. It does not modify historical results. ReportLab version and PDF metadata are fixed for reproducibility; review regenerated pages before committing. Runtime app dependencies do not include ReportLab.

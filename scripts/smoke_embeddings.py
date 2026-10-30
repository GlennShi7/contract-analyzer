"""Verify real PDF upload, CPU embeddings and persisted retrieval, without any LLM call.

Run against this repository's Compose stack. The first phase adds two synthetic
documents; --verify-only reads them without uploading again, including after
container recreation. Hugging Face weights may download during initial upload.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parents[1]

# Constant Python code passed as one argv item; all runtime values enter as JSON
# on stdin. No shell expansion, API client, /analyze or /ask request is involved.
INSPECT = r'''
from hashlib import sha256
import importlib.metadata
import json
import os
from pathlib import Path
import re
import sys
import struct

from chunker import chunk_text
from documents import load_document
from embedder import get_collection, search_chunks, MODEL_NAME

payload = json.load(sys.stdin)
collection = get_collection()
rows = []
texts = []
for document in payload['documents']:
    doc_id = document['doc_id']
    text = load_document(doc_id)
    texts.append(text)
    chunks = chunk_text(text)
    stored = collection.get(where={'doc_id': doc_id}, include=['documents', 'embeddings'])
    assert len(stored['ids']) == len(chunks) == document['n_chunks'], 'Chunk count changed or duplicate/stale chunks exist'
    stored_text = dict(zip(stored['ids'], stored['documents']))
    assert stored_text == {f'{doc_id}_chunk_{i}': chunk for i, chunk in enumerate(chunks)}, 'Stored chunks differ from parsed text'
    dimension = len(stored['embeddings'][0])
    assert dimension == 384, 'Unexpected multilingual MiniLM embedding dimension'
    vector_hash = sha256()
    for chunk_id, vector in sorted(zip(stored['ids'], stored['embeddings'])):
        vector_hash.update(chunk_id.encode())
        vector_hash.update(struct.pack('<384f', *vector))
    sources = search_chunks(payload['question'], doc_id, n_results=3)
    assert len(sources) == min(3, len(chunks)), 'Missing retrieval results'
    assert all(source['doc_id'] == doc_id and source['text'] == chunks[source['chunk']] for source in sources), 'Cross-document or corrupted retrieval'
    normalize = lambda value: re.sub(r'\s+', ' ', value).strip()
    hit = any(normalize(payload['answer_span']) in normalize(source['text']) for source in sources)
    print('SMOKE_OBSERVATION=' + json.dumps({'doc_id': doc_id, 'stored_vectors_sha256': vector_hash.hexdigest(), 'retrieved_chunks': [source['chunk'] for source in sources], 'fixed_question_hit_at_3': hit}), flush=True)
    assert hit, 'The fixed el01 answer span was not found in top-3 PDF chunks'
    rows.append({'doc_id': doc_id, 'n_chunks': len(chunks), 'text_sha256': sha256(text.encode()).hexdigest(),
                 'embedding_dimension': dimension, 'stored_vectors_sha256': vector_hash.hexdigest(), 'retrieved_chunks': [source['chunk'] for source in sources],
                 'foreign_chunks': 0, 'fixed_question_hit_at_3': hit})
assert len(texts) == 2 and texts[0] == texts[1], 'Byte variants must parse to the same synthetic text'
ref = Path(os.environ['HF_HOME']) / 'hub' / ('models--sentence-transformers--' + MODEL_NAME) / 'refs/main'
result = {'model': MODEL_NAME, 'model_revision': ref.read_text().strip() if ref.exists() else None,
          'runtime': {name: importlib.metadata.version(name) for name in ('torch', 'sentence-transformers', 'chromadb')},
          'offline_inspection': os.environ.get('HF_HUB_OFFLINE') == '1', 'rows': rows}
print('SMOKE_RESULT=' + json.dumps(result))
'''


def inspect(documents, question, answer_span, *, exclusive=False):
    if not exclusive:
        raise ValueError('Inspection requires --exclusive on an idle test stack; the backend is stopped briefly.')
    common = {'text': True, 'encoding': 'utf-8', 'errors': 'replace', 'capture_output': True, 'cwd': REPO}
    try:
        stopped = subprocess.run(['docker', 'compose', 'stop', '--timeout', '30', 'backend'], timeout=60, **common)
        if stopped.returncode:
            raise SystemExit('Cannot obtain exclusive backend storage access:\n' + stopped.stderr[-3000:])
        result = subprocess.run(
            ['docker', 'compose', 'run', '--rm', '--no-deps', '-T', '-e', 'HF_HUB_OFFLINE=1', 'backend', 'python', '-c', INSPECT],
            input=json.dumps({'documents': documents, 'question': question, 'answer_span': answer_span}),
            timeout=180, **common,
        )
    finally:
        restored = subprocess.run(['docker', 'compose', 'up', '-d', '--no-deps', '--wait', '--wait-timeout', '120', 'backend'], timeout=150, **common)
        if restored.returncode:
            raise SystemExit('Could not restore the test backend after inspection:\n' + restored.stderr[-3000:])
    if result.returncode:
        raise SystemExit('Container inspection failed:\n' + result.stdout[-6000:] + '\n' + result.stderr[-6000:])
    lines = [line.removeprefix('SMOKE_RESULT=') for line in result.stdout.splitlines() if line.startswith('SMOKE_RESULT=')]
    if len(lines) != 1:
        raise SystemExit('Container inspection did not return exactly one result.')
    report = json.loads(lines[0])
    if not report['offline_inspection']:
        raise SystemExit('Inspection must use the already-cached model offline.')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8080')
    parser.add_argument('--state', type=Path, required=True, help='synthetic test evidence written outside the repository')
    parser.add_argument('--verify-only', action='store_true', help='read saved documents and index without re-uploading')
    parser.add_argument('--exclusive', action='store_true', help='allow brief backend stops during inspection; use only on an idle test stack')
    args = parser.parse_args()
    if not args.exclusive:
        parser.error('--exclusive is required: inspection briefly stops and restores the backend; do not use on an active service.')
    pdf = (REPO / 'demo/lease_en.pdf').read_bytes()
    fixture = json.loads((REPO / 'demo/fixture.json').read_text(encoding='utf-8'))
    if sha256(pdf).hexdigest() != fixture['pdf_sha256']:
        raise SystemExit('Synthetic PDF checksum differs from its manifest.')
    variant = pdf + b'\n% synthetic integration-test byte variant\n'
    ids = [sha256(data).hexdigest() for data in (pdf, variant)]
    questions = [json.loads(line) for line in (REPO / 'backend/eval/questions.jsonl').read_text(encoding='utf-8').splitlines()]
    question = next(row for row in questions if row['id'] == 'el01')

    if args.verify_only:
        state = json.loads(args.state.read_text(encoding='utf-8'))
        documents = state['documents']
        if [row['doc_id'] for row in documents] != ids or any(not isinstance(row['n_chunks'], int) or row['n_chunks'] < 1 for row in documents):
            raise SystemExit('Saved smoke state does not match the two synthetic PDFs.')
        report = inspect(documents, question['question'], question['answer'][0], exclusive=args.exclusive)
        print(json.dumps({'phase': 'verify-only-observed', **report}), flush=True)
        if report != state['before_recreate']:
            print(json.dumps({'phase': 'persistence-comparison-failed', 'before': state['before_recreate'], 'after': report}), flush=True)
            raise SystemExit('Persisted text, model revision or retrieval changed after container recreation; both observations are logged above.')
        state['after_recreate'] = report
        args.state.write_text(json.dumps(state, indent=2) + '\n', encoding='utf-8')
        print('PASS: saved text, vectors and cached model survive recreation; identical top-3 retrieval offline. No uploads or LLM calls.')
        print(json.dumps({'phase': 'verify-only', **report}))
        return

    def upload(data, filename):
        boundary = 'contract-real-smoke-boundary'
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                f'Content-Type: application/pdf\r\n\r\n').encode() + data + f'\r\n--{boundary}--\r\n'.encode()
        req = Request(args.base_url.rstrip('/') + '/api/upload', data=body,
                      headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
        try:
            with urlopen(req, timeout=240) as response:
                uploaded = json.load(response)
        except HTTPError as error:
            raise SystemExit(f'Synthetic upload failed with HTTP {error.code}: {error.read().decode("utf-8", errors="replace")[:500]}') from None
        if uploaded.get('doc_id') != sha256(data).hexdigest() or not re.fullmatch(r'[0-9a-f]{64}', uploaded['doc_id']):
            raise SystemExit('Uploaded document ID is not its full PDF SHA-256.')
        if not isinstance(uploaded.get('n_chunks'), int) or uploaded['n_chunks'] < 1:
            raise SystemExit('Upload did not create any chunks.')
        return {'doc_id': uploaded['doc_id'], 'n_chunks': uploaded['n_chunks']}

    first = upload(pdf, 'lease.pdf')
    renamed = upload(pdf, 'renamed.pdf')
    if renamed != first:
        raise SystemExit('Renaming the same PDF changed its document or chunk count.')
    second = upload(variant, 'lease.pdf')
    documents = [first, second]
    report = inspect(documents, question['question'], question['answer'][0], exclusive=args.exclusive)
    state = {'fixture': 'two byte variants of committed synthetic PDF, identical parsed text',
             'documents': documents, 'question_id': 'el01', 'before_recreate': report,
             'limits': 'One fixed query is a smoke assertion, not a retrieval benchmark or a legal-accuracy result. No LLM call.'}
    args.state.parent.mkdir(parents=True, exist_ok=True)
    args.state.write_text(json.dumps(state, indent=2) + '\n', encoding='utf-8')
    print('PASS: real PDF parsing, idempotent upload, CPU embeddings and document-filtered top-3 for two identical-text documents. No LLM calls.')
    print(json.dumps({'phase': 'upload', **report}))


if __name__ == '__main__':
    main()

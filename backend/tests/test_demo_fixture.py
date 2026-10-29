from hashlib import sha256
import json
from pathlib import Path

from analyzer import match_quote, normalize_quote_whitespace
from chunker import chunk_text
from parser import extract_text


def test_demo_pdf_preserves_fixture_clauses_and_recorded_quotes():
    repo = Path(__file__).resolve().parents[2]
    metadata = json.loads((repo / 'demo/fixture.json').read_text(encoding='utf-8'))
    pdf = repo / 'demo/lease_en.pdf'
    source = (repo / metadata['text_source']).read_text(encoding='utf-8')
    assert sha256(pdf.read_bytes()).hexdigest() == metadata['pdf_sha256']
    assert sha256(source.encode()).hexdigest() == metadata['text_sha256']
    extracted = extract_text(str(pdf))
    assert 'DEMO FIXTURE' in extracted
    for paragraph in source.strip().split('\n\n'):
        assert normalize_quote_whitespace(paragraph) in normalize_quote_whitespace(extracted)
    result = json.loads((repo / metadata['analysis_source']).read_text(encoding='utf-8'))['rows'][0]['result']
    assert all(match_quote(card['clause_text'], extracted)[0] in {'exact', 'whitespace'} for card in result['cards'])
    chunks = chunk_text(source)
    assert metadata['n_chunks'] == len(chunks)
    for question in metadata['questions']:
        for excerpt in question['sources']:
            assert excerpt['text'] == chunks[excerpt['chunk']]

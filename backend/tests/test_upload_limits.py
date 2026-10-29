import io
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile
from chromadb.errors import InternalError
from embedder import EmbeddingUnavailableError


def test_real_pdf_page_boundaries_do_not_join_english_words(api, pdf_factory):
    import documents
    from analyzer import match_quote
    client, calls = api
    response = client.post('/upload', files={'file': ('pages.pdf', pdf_factory(['The tenant', '', 'must pay rent.']))})
    assert response.status_code == 200
    text = documents.load_document(response.json()['doc_id'])
    assert match_quote('The tenant must pay rent.', text)[0] == 'whitespace'
    assert 'tenantmust' not in text
    assert not calls


def test_oversized_upload_is_rejected_before_copying_or_parsing(api, monkeypatch):
    import main
    client, calls = api
    monkeypatch.setattr(main, 'MAX_UPLOAD_BYTES', 10)

    def forbidden(*args, **kwargs):
        raise AssertionError('An oversized declared file must not be copied or parsed')

    monkeypatch.setattr(main.tempfile, 'NamedTemporaryFile', forbidden)
    monkeypatch.setattr(main, 'extract_text', forbidden)
    assert client.post('/upload', files={'file': ('large.pdf', b'x' * 11)}).status_code == 413
    assert not calls


def test_stream_size_fallback_cleans_partial_temporary_file(api, monkeypatch):
    import main
    monkeypatch.setattr(main, 'MAX_UPLOAD_BYTES', 10)
    original = main.tempfile.NamedTemporaryFile
    paths = []

    def create(*args, **kwargs):
        handle = original(*args, **kwargs)
        paths.append(Path(handle.name))
        return handle

    monkeypatch.setattr(main.tempfile, 'NamedTemporaryFile', create)
    file = UploadFile(file=io.BytesIO(b'x' * 11), filename='large.pdf', size=None)
    with pytest.raises(HTTPException) as error:
        main.upload(file)
    assert error.value.status_code == 413
    assert len(paths) == 1 and not paths[0].exists()


def test_file_byte_limit_accepts_exact_boundary(api, pdf_factory, monkeypatch):
    import main
    client, _ = api
    data = pdf_factory('Lease text.')
    monkeypatch.setattr(main, 'MAX_UPLOAD_BYTES', len(data))
    assert client.post('/upload', files={'file': ('lease.pdf', data)}).status_code == 200
    monkeypatch.setattr(main, 'MAX_UPLOAD_BYTES', len(data) - 1)
    assert client.post('/upload', files={'file': ('lease.pdf', data)}).status_code == 413


def test_page_limit_rejects_real_multipage_pdf_without_indexing(api, pdf_factory, collection, monkeypatch):
    import parser
    client, calls = api
    monkeypatch.setattr(parser, 'MAX_PDF_PAGES', 1)
    response = client.post('/upload', files={'file': ('two.pdf', pdf_factory(['First page.', 'Second page.']))})
    assert response.status_code == 413
    assert '页' in response.json()['detail']
    assert collection.count() == 0
    assert not calls


def test_extracted_text_limit_accepts_boundary_and_rejects_larger_pdf(api, pdf_factory, collection, monkeypatch):
    import parser
    client, calls = api
    monkeypatch.setattr(parser, 'MAX_DOCUMENT_CHARS', 5)
    assert client.post('/upload', files={'file': ('ok.pdf', pdf_factory('12345'))}).status_code == 200
    response = client.post('/upload', files={'file': ('long.pdf', pdf_factory('123456'))})
    assert response.status_code == 413
    assert '字符' in response.json()['detail']
    assert collection.count() == 1
    assert not calls


def test_legacy_oversized_analysis_is_rejected_before_generation(api, monkeypatch):
    import main
    client, calls = api
    monkeypatch.setattr(main, 'contract_text', lambda doc_id: 'x' * (main.MAX_DOCUMENT_CHARS + 1))
    response = client.post('/analyze', json={'doc_id': 'a' * 64})
    assert response.status_code == 413
    assert not calls


def test_wrapped_password_error_is_explained(api, monkeypatch):
    import main
    from pdfminer.pdfdocument import PDFPasswordIncorrect
    from pdfplumber.utils.exceptions import PdfminerException
    client, calls = api

    def encrypted(path):
        try:
            raise PDFPasswordIncorrect()
        except PDFPasswordIncorrect as error:
            raise PdfminerException(error)

    monkeypatch.setattr(main, 'extract_text', encrypted)
    response = client.post('/upload', files={'file': ('encrypted.pdf', b'fixture')})
    assert response.status_code == 400
    assert '先解锁' in response.json()['detail']
    assert not calls


@pytest.mark.parametrize('endpoint', ['/upload', '/ask'])
@pytest.mark.parametrize('failure', [EmbeddingUnavailableError, InternalError])
def test_index_unavailability_returns_503_without_generation(api, pdf_factory, monkeypatch, endpoint, failure):
    import main
    client, calls = api

    def unavailable(*args, **kwargs):
        raise failure('index unavailable')

    if endpoint == '/upload':
        monkeypatch.setattr(main, 'store_chunks', unavailable)
        response = client.post(endpoint, files={'file': ('lease.pdf', pdf_factory('Lease text.'))})
    else:
        monkeypatch.setattr(main, 'contract_text', lambda doc_id: 'Lease text.')
        monkeypatch.setattr(main, 'search_chunks', unavailable)
        response = client.post(endpoint, json={'doc_id': 'a' * 64, 'question': 'deposit?'})
    assert response.status_code == 503
    assert '嵌入模型' in response.json()['detail']
    assert not calls


@pytest.mark.parametrize('endpoint', ['/analyze', '/ask'])
def test_unreadable_saved_text_returns_503_before_generation(api, monkeypatch, endpoint):
    import main
    client, calls = api

    def unavailable(doc_id):
        raise PermissionError('storage unavailable')

    monkeypatch.setattr(main, 'load_document', unavailable)
    response = client.post(endpoint, json={'doc_id': 'a' * 64, 'question': 'deposit?'})
    assert response.status_code == 503
    assert '无法读取' in response.json()['detail']
    assert not calls


def test_failed_text_save_can_be_retried_without_duplicate_vectors(api, pdf_factory, collection, monkeypatch):
    import main
    client, calls = api
    save = main.save_document

    def unavailable(*args, **kwargs):
        raise OSError('storage unavailable')

    monkeypatch.setattr(main, 'save_document', unavailable)
    data = pdf_factory('Lease text.')
    response = client.post('/upload', files={'file': ('lease.pdf', data)})
    assert response.status_code == 503
    assert '存储' in response.json()['detail']
    assert collection.count() == 1
    monkeypatch.setattr(main, 'save_document', save)
    assert client.post('/upload', files={'file': ('lease.pdf', data)}).status_code == 200
    assert collection.count() == 1
    assert not calls


@pytest.mark.parametrize('failure', [OSError, RuntimeError, ValueError])
def test_model_initialization_failure_does_not_poison_retry_cache(monkeypatch, failure):
    import embedder
    calls = []
    model = object()

    def load(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise failure('model unavailable')
        return model

    embedder.get_embedding_function.cache_clear()
    monkeypatch.setattr(embedder.embedding_functions, 'SentenceTransformerEmbeddingFunction', load)
    try:
        with pytest.raises(embedder.EmbeddingUnavailableError):
            embedder.get_embedding_function()
        assert embedder.get_embedding_function() is model
        assert embedder.get_embedding_function() is model
        assert len(calls) == 2
    finally:
        embedder.get_embedding_function.cache_clear()

"""Check the local Compose HTTP path without model downloads or billable calls."""
import argparse
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8080')
    args = parser.parse_args()
    base = args.base_url.rstrip('/')

    def request(path, expected=200, *, data=None, content_type=None):
        headers = {'Content-Type': content_type} if content_type else {}
        req = Request(base + path, data=data, headers=headers)
        try:
            with urlopen(req, timeout=15) as response:
                status, body = response.status, response.read().decode('utf-8')
        except HTTPError as error:
            status, body = error.code, error.read().decode('utf-8')
        if status != expected:
            raise SystemExit(f'{path}: expected HTTP {expected}, received {status}')
        return body

    assert 'id="root"' in request('/')
    assert json.loads(request('/api/hello'))['message']
    schema = json.loads(request('/api/openapi.json'))
    assert {'/upload', '/analyze', '/ask'} <= set(schema['paths'])
    assert {'url': '/api'} in schema.get('servers', [])
    assert '/api/openapi.json' in request('/api/docs')
    request('/api/analyze', 422, data=json.dumps({'doc_id': 'invalid'}).encode(), content_type='application/json')
    request('/api/unknown-route', 404)
    request('/api/ask', 422, data=json.dumps({'doc_id': 'a' * 64, 'question': '   '}).encode(), content_type='application/json')
    boundary = 'contract-smoke-boundary'
    invalid_pdf = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="invalid.pdf"\r\n'
                   f'Content-Type: application/pdf\r\n\r\nnot a PDF\r\n--{boundary}--\r\n').encode()
    request('/api/upload', 400, data=invalid_pdf, content_type=f'multipart/form-data; boundary={boundary}')
    print('PASS: frontend, reverse proxy, health, OpenAPI/docs prefix, validation, unknown route and invalid PDF. No LLM calls.')


if __name__ == '__main__':
    main()

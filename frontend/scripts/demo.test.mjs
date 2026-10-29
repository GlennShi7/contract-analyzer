import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { startDemo } from './demo.mjs';

test('replay serves only its fixed synthetic fixture, recorded analysis and scripted questions', async () => {
  const server = await startDemo({ port: 0 });
  try {
    const base = `http://127.0.0.1:${server.httpServer.address().port}`;
    const post = (route, body) => fetch(base + '/demo-api/' + route, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    const download = await fetch(base + '/demo/lease_en.pdf');
    assert.equal(download.headers.get('content-type'), 'application/pdf');
    const pdf = Buffer.from(await download.arrayBuffer());
    assert.equal(pdf.subarray(0, 5).toString(), '%PDF-');
    const doc_id = createHash('sha256').update(pdf).digest('hex');
    let form = new FormData();
    form.append('file', new Blob(['not the fixture']), 'other.pdf');
    assert.equal((await fetch(base + '/demo-api/upload', { method: 'POST', body: form })).status, 400);
    form = new FormData();
    form.append('file', new Blob([pdf], { type: 'application/pdf' }), 'renamed.pdf');
    const uploaded = await (await fetch(base + '/demo-api/upload', { method: 'POST', body: form })).json();
    assert.equal(uploaded.doc_id, doc_id);
    assert.equal(uploaded.filename, 'renamed.pdf');
    assert.equal((await post('analyze', { doc_id, jurisdiction: 'cn' })).status, 422);
    const result = await (await post('analyze', { doc_id, jurisdiction: 'us_il_urbana' })).json();
    const original = JSON.parse(await readFile(new URL('../../backend/eval/results/analysis_20261028-161231.json', import.meta.url), 'utf8'));
    assert.deepEqual(result.result, original.rows.find(row => row.contract === 'lease_en').result);
    for (const question of ['押金多久退还？', '会自动续租吗？']) {
      const answer = await (await post('ask', { doc_id, question })).json();
      assert.ok(answer.answer.startsWith('预设示例：'));
      assert.ok(answer.sources.every(source => source.doc_id === doc_id));
    }
    assert.equal((await post('ask', { doc_id, question: '其他问题' })).status, 422);
    assert.equal((await post('ask', { doc_id: 'a'.repeat(64), question: '押金多久退还？' })).status, 404);
  } finally { await server.close(); }
});

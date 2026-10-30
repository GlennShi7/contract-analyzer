// Local replay only: no SDK, API key, Python backend or embedding model is used.
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { createServer } from 'vite';

const frontend = fileURLToPath(new URL('..', import.meta.url));
const repo = path.resolve(frontend, '..');
const digest = bytes => createHash('sha256').update(bytes).digest('hex');

export async function startDemo({ port = 5174 } = {}) {
  const fixture = JSON.parse(await readFile(path.join(repo, 'demo/fixture.json'), 'utf8'));
  const pdf = await readFile(path.join(repo, 'demo/lease_en.pdf'));
  const run = JSON.parse(await readFile(path.join(repo, fixture.analysis_source), 'utf8'));
  const recorded = run.rows.find(row => row.contract === 'lease_en');
  if (digest(pdf) !== fixture.pdf_sha256 || recorded?.text_sha256 !== fixture.text_sha256) {
    throw new Error('Demo fixture does not match the recorded synthetic contract.');
  }
  const docId = fixture.pdf_sha256;
  process.env.VITE_API_URL = '/demo-api';
  process.env.VITE_REPLAY_DEMO = 'true';

  const server = await createServer({ root: frontend, server: { host: '127.0.0.1', port, strictPort: true },
    plugins: [{ name: 'synthetic-replay', configureServer(vite) {
      vite.middlewares.use(async (req, res, next) => {
        const pathname = new URL(req.url, 'http://127.0.0.1').pathname;
        if (pathname === '/demo/lease_en.pdf' && req.method === 'GET') {
          res.setHeader('Content-Type', 'application/pdf');
          res.setHeader('Content-Disposition', 'attachment; filename="synthetic-urbana-lease.pdf"');
          res.end(pdf); return;
        }
        if (!pathname.startsWith('/demo-api/')) { next(); return; }
        const reply = (status, value) => {
          res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' });
          res.end(JSON.stringify(value));
        };
        try {
          if (req.method !== 'POST') { reply(405, { detail: '演示接口只接受 POST。' }); return; }
          const body = await new Promise((resolve, reject) => {
            let size = 0;
            const chunks = [];
            req.on('data', chunk => {
              size += chunk.length;
              if (size > 2 * 1024 * 1024) { reject(new Error('too large')); return; }
              chunks.push(chunk);
            });
            req.on('end', () => resolve(Buffer.concat(chunks)));
            req.on('error', reject);
          });
          if (pathname === '/demo-api/upload') {
            const form = await new Request('http://127.0.0.1/upload', { method: 'POST',
              headers: { 'Content-Type': req.headers['content-type'] || '' }, body }).formData();
            const file = form.get('file');
            if (!file || typeof file.arrayBuffer !== 'function' || digest(Buffer.from(await file.arrayBuffer())) !== docId) {
              reply(400, { detail: '回放仅支持页面提供的合成演示 PDF；请下载后上传该文件。' }); return;
            }
            reply(200, { doc_id: docId, filename: file.name, preview: fixture.preview, n_chunks: fixture.n_chunks }); return;
          }
          const data = JSON.parse(body.toString('utf8'));
          if (data?.doc_id !== docId) { reply(404, { detail: '请先上传指定的合成演示 PDF。' }); return; }
          if (pathname === '/demo-api/analyze') {
            if (data.jurisdiction !== 'us_il_urbana') {
              reply(422, { detail: '此回放样例请先选择“美国 · Urbana, Illinois”。' }); return;
            }
            reply(200, { doc_id: docId, result: recorded.result }); return;
          }
          if (pathname === '/demo-api/ask') {
            const aliases = { 'When is the deposit returned?': '押金多久退还？', 'Does the lease renew automatically?': '会自动续租吗？' };
            const question = data.question?.trim();
            const preset = fixture.questions.find(item => item.question === (aliases[question] || question));
            if (!preset) { reply(422, { detail: '此回放仅支持“押金多久退还？”和“会自动续租吗？”两个预设问题。' }); return; }
            reply(200, { doc_id: docId, answer: preset.answer, sources: preset.sources.map(source => ({ ...source, doc_id: docId })) }); return;
          }
          reply(404, { detail: '未提供该演示接口。' });
        } catch (error) {
          reply(error.message === 'too large' ? 413 : 400, { detail: '无法读取演示请求；请使用指定样例。' });
        }
      });
    } }],
  });
  await server.listen();
  return server;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const server = await startDemo();
  console.log('Recorded-analysis replay + scripted Q&A. No model/API calls.');
  console.log('Open http://127.0.0.1:5174 and download the supplied synthetic PDF.');
  for (const signal of ['SIGINT', 'SIGTERM']) process.once(signal, async () => { await server.close(); });
}

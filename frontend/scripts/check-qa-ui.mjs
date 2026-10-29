// Actual React UI checks against a local mock API. No paid model calls.
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { mkdir, mkdtemp, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const frontend = fileURLToPath(new URL('..', import.meta.url));
const out = process.env.QA_UI_OUTPUT || await mkdtemp(path.join(tmpdir(), 'contract-qa-ui-'));
await mkdir(out, { recursive: true });
const requests = [];
const browserErrors = [];
let uploads = 0;
let delayed;
let aborted = false;
const api = createServer(async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', 'http://127.0.0.1:18764');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  if (req.url === '/upload') {
    const doc_id = (++uploads === 1 ? 'a' : 'b').repeat(64);
    res.end(JSON.stringify({ doc_id, filename: 'lease.pdf', preview: 'Synthetic contract preview', n_chunks: 2 }));
    return;
  }
  if (req.url !== '/ask') { res.writeHead(404); res.end('{}'); return; }
  const payload = JSON.parse(Buffer.concat(chunks).toString());
  requests.push(payload);
  if (payload.question === '等待回答') {
    delayed = res;
    res.on('close', () => { if (!res.writableEnded) aborted = true; });
    return;
  }
  const errors = { '索引丢失': [409, '合同索引不可用，请重新上传'], '服务失败': [502, '问答服务暂时不可用，请稍后重试'], '合同不存在': [404, '未找到合同，请先上传或重新上传'] };
  if (errors[payload.question]) {
    const [status, detail] = errors[payload.question];
    res.writeHead(status); res.end(JSON.stringify({ detail })); return;
  }
  if (payload.question === '错误格式') { res.end('not json'); return; }
  res.end(JSON.stringify({ doc_id: payload.doc_id,
    answer: payload.question === '空回答' ? ' ' : `合同约定搬出后10日内退还押金。【合同原文1】\n当前合同：${payload.doc_id[0]}`,
    sources: [{ doc_id: payload.question === '混入其他合同' ? 'c'.repeat(64) : payload.doc_id, chunk: 0,
      text: payload.question === '混入其他合同' ? 'FOREIGN_SECRET_MUST_NOT_RENDER' : 'Security deposit is returned within 10 days after move-out.' },
      { doc_id: payload.doc_id, chunk: 1, text: '<script>window.qaInjected = true</script>\nThis is literal contract text, not HTML.' }],
  }));
});

let vite;
let browser;
let socket;
let counter = 0;
const waiting = new Map();

const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
function send(method, params = {}) {
  const id = ++counter;
  return new Promise((resolve, reject) => {
    waiting.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression) {
  const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}
async function until(expression) {
  for (let i = 0; i < 100; i++) {
    if (await evaluate(expression)) return;
    await pause(100);
  }
  throw new Error('UI condition timed out: ' + expression);
}
async function screenshot(name) {
  const metrics = await send('Page.getLayoutMetrics');
  const size = metrics.cssContentSize;
  const result = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true,
    clip: { x: 0, y: 0, width: Math.ceil(size.width), height: Math.ceil(size.height), scale: 1 } });
  await writeFile(path.join(out, name), Buffer.from(result.data, 'base64'));
}
async function fill(question) {
  await evaluate(`(() => { const el = document.querySelector('#contract-question'); Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(el, ${JSON.stringify(question)}); el.dispatchEvent(new Event('input', {bubbles: true})); })()`);
}
async function submit(question) {
  await fill(question);
  await evaluate('document.querySelector(".contract-questions form").requestSubmit()');
}
async function upload(filename) {
  const fixture = path.join(out, filename);
  await writeFile(fixture, '%PDF-1.4\nSynthetic browser fixture. PDF parsing is covered separately.');
  const doc = await send('DOM.getDocument');
  const input = await send('DOM.querySelector', { nodeId: doc.root.nodeId, selector: 'input[type=file]' });
  await send('DOM.setFileInputFiles', { nodeId: input.nodeId, files: [fixture] });
  if (await evaluate('Boolean(document.querySelector(".contract-questions"))')) throw new Error('Selecting another file retained Q&A');
  await evaluate('Array.from(document.querySelectorAll("button")).find(b => b.textContent === "上传").click()');
  await until('Boolean(document.querySelector("#contract-question"))');
}

try {
  await new Promise((resolve, reject) => { api.once('error', reject); api.listen(18765, '127.0.0.1', resolve); });
  process.env.VITE_API_URL = 'http://127.0.0.1:18765';
  const { createServer: createViteServer } = await import(pathToFileURL(path.join(frontend, 'node_modules/vite/dist/node/index.js')));
  vite = await createViteServer({ root: frontend, server: { host: '127.0.0.1', port: 18764, strictPort: true } });
  await vite.listen();
  const executable = process.env.EDGE_PATH || String.raw`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`;
  const browserProfile = await mkdtemp(path.join(out, 'browser-profile-'));
  browser = spawn(executable, ['--headless', '--disable-gpu', '--disable-background-networking', '--disable-component-update',
    '--no-first-run', '--no-default-browser-check', '--remote-debugging-port=0',
    `--user-data-dir=${browserProfile}`, 'about:blank'], { windowsHide: true, stdio: 'ignore' });
  let launchError;
  browser.on('error', error => { launchError = error; });
  let target;
  for (let i = 0; i < 100; i++) {
    if (launchError) throw launchError;
    try {
      const port = Number((await readFile(path.join(browserProfile, 'DevToolsActivePort'), 'utf8')).split('\n')[0]);
      if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Invalid owned-browser debug port');
      target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json();
      break;
    }
    catch { await pause(100); }
  }
  if (!target) throw new Error('Edge did not start; set EDGE_PATH if needed.');
  socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { socket.addEventListener('open', resolve, { once: true }); socket.addEventListener('error', reject, { once: true }); });
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.method === 'Runtime.consoleAPICalled' && message.params.type === 'error') browserErrors.push(message.params.args.map(arg => arg.value || arg.description).join(' '));
    if (message.method === 'Runtime.exceptionThrown') browserErrors.push(message.params.exceptionDetails.text);
    const pending = waiting.get(message.id);
    if (!pending) return;
    waiting.delete(message.id);
    if (message.error) pending.reject(new Error(JSON.stringify(message.error)));
    else pending.resolve(message.result);
  });
  await send('Page.enable');
  await send('Runtime.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: 1200, height: 1000, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: 'http://127.0.0.1:18764' });
  await until('Boolean(document.querySelector("input[type=file]"))');
  if (await evaluate('Boolean(document.querySelector(".contract-questions"))')) throw new Error('Q&A shown before upload');
  await upload('first.pdf');
  if (!(await evaluate('document.querySelector(".contract-questions button").disabled'))) throw new Error('Empty question enabled');
  await submit('   ');
  if (requests.length) throw new Error('Whitespace question sent');
  await submit('  押金什么时候退？  ');
  await until('Boolean(document.querySelector("[aria-label=合同问答结果]"))');
  if (requests[0].doc_id !== 'a'.repeat(64) || requests[0].question !== '押金什么时候退？') throw new Error('Wrong document or untrimmed question');
  await evaluate('document.querySelectorAll(".contract-questions details").forEach(el => el.open = true)');
  if ((await evaluate('document.querySelectorAll(".contract-questions blockquote").length')) !== 2) throw new Error('Missing source excerpts');
  if (await evaluate('Boolean(document.querySelector(".contract-questions script")) || Boolean(window.qaInjected)')) throw new Error('Contract source interpreted as HTML');
  await screenshot('qa-desktop.png');
  for (const [question, expected] of [['索引丢失', '合同索引不可用'], ['服务失败', '问答服务暂时不可用'], ['合同不存在', '未找到合同'], ['混入其他合同', '对应信息不完整'], ['空回答', '未收到有效回答'], ['错误格式', '无法读取问答结果']]) {
    await submit(question);
    await until(`document.querySelector('.contract-questions [role=alert]')?.textContent.includes(${JSON.stringify(expected)})`);
    if (await evaluate('Boolean(document.querySelector("[aria-label=合同问答结果]")) || document.body.innerText.includes("FOREIGN_SECRET_MUST_NOT_RENDER")')) throw new Error('Stale or foreign answer shown');
  }
  await fill('等待回答');
  const before = requests.length;
  await evaluate('document.querySelector(".contract-questions form").requestSubmit(); document.querySelector(".contract-questions form").requestSubmit();');
  await until('document.querySelector(".contract-questions button").disabled && document.body.innerText.includes("正在查找相关约定")');
  for (let i = 0; i < 100 && !delayed; i++) await pause(50);
  if (!delayed || requests.length !== before + 1) throw new Error('Duplicate submission or no pending request');
  await upload('second.pdf');
  if (await evaluate('document.querySelector("#contract-question").value !== "" || Boolean(document.querySelector("[aria-label=合同问答结果]"))')) throw new Error('Q&A not reset');
  for (let i = 0; i < 100 && !aborted; i++) await pause(50);
  if (!aborted) throw new Error('Pending request was not aborted');
  delayed.end(JSON.stringify({ answer: 'OLD_ANSWER_MUST_NOT_RENDER' }));
  await submit('第二份合同押金什么时候退？');
  await until('Boolean(document.querySelector("[aria-label=合同问答结果]"))');
  if (requests.at(-1).doc_id !== 'b'.repeat(64) || await evaluate('document.body.innerText.includes("OLD_ANSWER_MUST_NOT_RENDER")')) throw new Error('Cross-document response leakage');
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  await evaluate('document.querySelectorAll(".contract-questions details").forEach(el => el.open = true)');
  if (!(await evaluate('(() => { const r = document.querySelector(".contract-questions").getBoundingClientRect(); return r.left >= 0 && r.right <= window.innerWidth + 1; })()'))) throw new Error('Q&A overflows mobile viewport');
  await screenshot('qa-mobile.png');
  if (browserErrors.length) throw new Error('Browser errors: ' + browserErrors.join('\n'));
  await writeFile(path.join(out, 'checks.json'), JSON.stringify({ mode: 'local mock API; no model API calls', checks: ['upload required', 'trimmed questions', 'whitespace rejected', 'document-scoped answer and sources', 'literal text rendering', '409/502/404 errors', 'foreign source rejected', 'blank answer rejected', 'invalid JSON', 'duplicate submit blocked', 'file change clears state and aborts pending fetch', 'new document ID sent', 'mobile width'], requests }, null, 2));
  console.log('PASS: actual contract Q&A UI checks; no paid API calls.');
  console.log('Artifacts:', out);
} finally {
  try { if (socket?.readyState === WebSocket.OPEN) await send('Browser.close'); } catch {}
  socket?.close();
  browser?.kill();
  await vite?.close();
  api.closeAllConnections();
  await new Promise(resolve => api.close(resolve));
}

// Actual React UI checks against a local mock API. No paid model calls.
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { mkdir, mkdtemp, open, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const frontend = fileURLToPath(new URL('..', import.meta.url));
const out = process.env.QA_UI_OUTPUT || await mkdtemp(path.join(tmpdir(), 'contract-qa-ui-'));
await mkdir(out, { recursive: true });
const requests = [];
const browserErrors = [];
let uploads = 0;
let uploadRequests = 0;
let uploadMode = 'ok';
let delayed;
let aborted = false;
const analysisRequests = [];
let analysisMode = 'ok';
let delayedAnalysis;
let analysisAborted = false;
const analysisResult = { risk_score: 3, summary: 'ORIGINAL_SUMMARY',
  cards: [{ title: 'Synthetic risk', clause_text: 'Original contract clause.', risk_level: 'medium', explanation: 'Synthetic explanation',
    suggestion: 'Synthetic suggestion', verified: true, legal_basis: ['law1'] }],
  legal_sources: [{ id: 'law1', law: 'Synthetic law', article: 'Section 1', text: '<script>window.reportInjected = true</script>',
    source_url: 'https://www.ilga.gov/', checked_on: '2026-10-30', authority_level: 'state', applicability: 'Synthetic condition' }],
  legal_scope: 'Synthetic scope', disclaimer: 'Synthetic disclaimer' };
const malformedReports = {
  missing: undefined, null: null, cards: { ...analysisResult, cards: {} }, score: { ...analysisResult, risk_score: '3' },
  summary: { ...analysisResult, summary: { text: 'wrong type' } },
  card: { ...analysisResult, cards: [null] },
  basis: { ...analysisResult, cards: [{ ...analysisResult.cards[0], legal_basis: null }] },
  verified: { ...analysisResult, cards: [{ ...analysisResult.cards[0], verified: 'false' }] },
  level: { ...analysisResult, cards: [{ ...analysisResult.cards[0], risk_level: '__proto__' }] },
  sources: { ...analysisResult, legal_sources: {} }, source: { ...analysisResult, legal_sources: [null] },
  reference: { ...analysisResult, legal_sources: [] },
  duplicate: { ...analysisResult, legal_sources: [analysisResult.legal_sources[0], analysisResult.legal_sources[0]] },
  link: { ...analysisResult, legal_sources: [{ ...analysisResult.legal_sources[0], source_url: 'javascript:window.reportInjected = true' }] },
  scope: { ...analysisResult, legal_scope: 1 },
  authority: { ...analysisResult, legal_sources: [{ ...analysisResult.legal_sources[0], authority_level: 'constructor' }] },
};
const api = createServer(async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', 'http://127.0.0.1:18764');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  if (req.url === '/upload') {
    uploadRequests++;
    if (uploadMode === 'html413') {
      res.setHeader('Content-Type', 'text/html'); res.writeHead(413); res.end('<h1>Request too large</h1>'); return;
    }
    if (uploadMode === 'index503') {
      res.writeHead(503); res.end(JSON.stringify({ detail: '合同索引服务暂时不可用，首次使用需要下载嵌入模型' })); return;
    }
    if (uploadMode === 'untranslated') { res.writeHead(503); res.end(JSON.stringify({ detail: '自定义服务提示：维护中' })); return; }
    if (uploadMode === 'invalid') { res.end(JSON.stringify({ preview: 'Incomplete response' })); return; }
    const doc_id = (++uploads === 1 ? 'a' : 'b').repeat(64);
    res.end(JSON.stringify({ doc_id, filename: 'lease.pdf', preview: 'Synthetic contract preview', n_chunks: 2 }));
    return;
  }
  if (req.url === '/analyze') {
    const payload = JSON.parse(Buffer.concat(chunks).toString());
    analysisRequests.push(payload);
    if (analysisMode === 'pending') {
      delayedAnalysis = res;
      res.on('close', () => { if (!res.writableEnded) analysisAborted = true; });
      return;
    }
    if (analysisMode === 'error') { res.writeHead(502); res.end(JSON.stringify({ detail: '分析服务暂时不可用，请稍后重试' })); return; }
    if (analysisMode === 'empty') { res.end(JSON.stringify({ doc_id: payload.doc_id, result: { ...analysisResult, cards: [], legal_sources: [] } })); return; }
    if (analysisMode === 'html') { res.end('<h1>Unavailable</h1>'); return; }
    if (Object.hasOwn(malformedReports, analysisMode)) { res.end(JSON.stringify({ doc_id: payload.doc_id, result: malformedReports[analysisMode] })); return; }
    res.end(JSON.stringify({ doc_id: analysisMode === 'foreign' ? 'c'.repeat(64) : payload.doc_id,
      result: { ...analysisResult, summary: analysisMode === 'foreign' ? 'FOREIGN_REPORT_MUST_NOT_RENDER' : analysisResult.summary } }));
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
async function upload(filename, expectedError) {
  const fixture = path.join(out, filename);
  await writeFile(fixture, '%PDF-1.4\nSynthetic browser fixture. PDF parsing is covered separately.');
  const doc = await send('DOM.getDocument');
  const input = await send('DOM.querySelector', { nodeId: doc.root.nodeId, selector: 'input[type=file]' });
  await send('DOM.setFileInputFiles', { nodeId: input.nodeId, files: [fixture] });
  if (await evaluate('Boolean(document.querySelector(".contract-questions"))')) throw new Error('Selecting another file retained Q&A');
  const before = uploadRequests;
  await evaluate('(() => { const b = document.querySelector(".upload-actions button"); b.click(); b.click(); })()');
  if (expectedError) {
    await until(`Array.from(document.querySelectorAll('[role=alert]')).some(el => el.textContent.includes(${JSON.stringify(expectedError)}))`);
    if (await evaluate('Boolean(document.querySelector("#contract-question"))')) throw new Error('Failed upload created document UI');
  } else {
    await until('Boolean(document.querySelector("#contract-question"))');
  }
  if (uploadRequests !== before + 1) throw new Error('Duplicate upload request');
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
  if (!(await evaluate('document.documentElement.lang === "en" && document.querySelector("h1").textContent === "Read the terms. See what matters."'))) throw new Error('English is not the default UI');

  for (const width of [320, 390, 768, 1200]) {
    await send('Emulation.setDeviceMetricsOverride', { width, height: width < 640 ? 844 : 1000, deviceScaleFactor: 1, mobile: width < 880 });
    if (!(await evaluate(`document.documentElement.scrollWidth <= ${width} + 1`))) throw new Error(`Home page overflows at ${width}px`);
    if (width === 390) await screenshot('workspace-empty-mobile.png');
  }
  if (!(await evaluate('document.querySelector("input[type=file]").labels.length > 0'))) throw new Error('File picker has no label');
  await screenshot('workspace-empty-desktop.png');
  await evaluate('document.querySelector("[data-language-toggle]").click()');
  await until('document.documentElement.lang === "zh-CN"');
  await send('Page.reload'); await pause(200);
  await until('document.documentElement.lang === "zh-CN" && Boolean(document.querySelector("input[type=file]"))');
  await evaluate('document.querySelector("[data-language-toggle]").click()');
  await until('document.documentElement.lang === "en"');
  await send('Page.reload'); await pause(200);
  await until('document.documentElement.lang === "en" && Boolean(document.querySelector("input[type=file]"))');
  if (requests.length || uploadRequests) throw new Error('Language preference triggered an API request');

  const oversized = path.join(out, 'oversized.pdf');
  const oversizedFile = await open(oversized, 'w');
  await oversizedFile.truncate(20 * 1024 * 1024 + 1);
  await oversizedFile.close();
  const initialDoc = await send('DOM.getDocument');
  const initialInput = await send('DOM.querySelector', { nodeId: initialDoc.root.nodeId, selector: 'input[type=file]' });
  await send('DOM.setFileInputFiles', { nodeId: initialInput.nodeId, files: [oversized] });
  await until('document.querySelector("[role=alert]")?.textContent.includes("20 MiB")');
  if (uploadRequests !== 0 || !(await evaluate('document.querySelector(".upload-actions button").disabled'))) throw new Error('Oversized file sent to API');
  if (!(await evaluate('document.querySelector("[role=alert]").textContent.includes("The PDF exceeds 20 MiB")'))) throw new Error('English upload error missing');
  await evaluate('document.querySelector("[data-language-toggle]").click()');
  await until('document.documentElement.lang === "zh-CN" && document.querySelector("[role=alert]").textContent.includes("PDF 文件不能超过")');
  uploadMode = 'html413';
  await upload('proxy-limit.pdf', '文件或请求过大');
  uploadMode = 'index503';
  await upload('cache-error.pdf', '嵌入模型');
  uploadMode = 'invalid';
  await upload('invalid-response.pdf', '上传结果不完整');
  await evaluate('document.querySelector("[data-language-toggle]").click()');
  await until('document.documentElement.lang === "en"');
  uploadMode = 'untranslated';
  await upload('unknown-service.pdf', 'Upload failed');
  if (!(await evaluate('document.querySelector("[role=alert] > p").textContent === "Upload failed. Please try again." && document.querySelector("[role=alert] details p").textContent === "自定义服务提示：维护中"'))) throw new Error('Unknown server detail was lost or mistranslated');
  await evaluate('document.querySelector("[data-language-toggle]").click()');
  await until('document.documentElement.lang === "zh-CN"');
  uploadMode = 'ok';
  await upload('first.pdf');
  if (!(await evaluate('document.querySelector(".contract-questions button").disabled'))) throw new Error('Empty question enabled');
  const beforeSuggestion = requests.length;
  await evaluate('document.querySelector(".question-suggestions button").click()');
  await until('document.querySelector("#contract-question").value === "押金多久退还？"');
  if (requests.length !== beforeSuggestion || !(await evaluate('document.activeElement.id === "contract-question"'))) throw new Error('Suggestion sent a request or did not focus the question');
  await fill('');
  await until('document.querySelector(".contract-questions button").disabled');

  await submit('   ');
  if (requests.length) throw new Error('Whitespace question sent');
  await submit('  押金什么时候退？  ');
  await until('Boolean(document.querySelector("[aria-label=合同问答结果]"))');
  if (requests[0].doc_id !== 'a'.repeat(64) || requests[0].question !== '押金什么时候退？') throw new Error('Wrong document or untrimmed question');
  await evaluate('document.querySelectorAll(".contract-questions details").forEach(el => el.open = true)');
  if ((await evaluate('document.querySelectorAll(".contract-questions blockquote").length')) !== 2) throw new Error('Missing source excerpts');
  if (await evaluate('Boolean(document.querySelector(".contract-questions script")) || Boolean(window.qaInjected)')) throw new Error('Contract source interpreted as HTML');
  await submit('押金返还期限是多少？');
  await until('document.querySelectorAll("[data-qa-status=complete]").length === 2');
  if (!(await evaluate('document.querySelector(".question-history").innerText.includes("押金什么时候退？") && document.querySelector(".question-history").innerText.includes("押金返还期限是多少？")'))) throw new Error('Prior question lost');
  if (Object.keys(requests.at(-1)).sort().join(',') !== 'doc_id,question') throw new Error('Unexpected conversation history sent to API');
  const originalAnswers = await evaluate('Array.from(document.querySelectorAll(".contract-answer")).map(el => el.textContent)');
  const beforeLanguage = requests.length;
  await evaluate('document.querySelector("[data-language-toggle]").click()');
  await until('document.documentElement.lang === "en"');
  if (JSON.stringify(await evaluate('Array.from(document.querySelectorAll(".contract-answer")).map(el => el.textContent)')) !== JSON.stringify(originalAnswers) || requests.length !== beforeLanguage) throw new Error('Language switch changed answers or sent requests');
  await screenshot('qa-desktop.png');
  await evaluate('document.querySelector("[data-language-toggle]").click()');
  await until('document.documentElement.lang === "zh-CN"');
  for (const [question, expected] of [['索引丢失', '合同索引不可用'], ['服务失败', '问答服务暂时不可用'], ['合同不存在', '未找到合同'], ['混入其他合同', '对应信息不完整'], ['空回答', '未收到有效回答'], ['错误格式', '无法读取问答结果']]) {
    await submit(question);
    await until(`document.querySelector('.question-history > li:last-child [role=alert]')?.textContent.includes(${JSON.stringify(expected)})`);
    if (await evaluate('Boolean(document.querySelector(".question-history > li:last-child .contract-answer")) || document.body.innerText.includes("FOREIGN_SECRET_MUST_NOT_RENDER")')) throw new Error('Failed question contains stale or foreign answer');
    if ((await evaluate('document.querySelectorAll("[data-qa-status=complete]").length')) !== 2) throw new Error('Failure removed prior answers');
  }
  await fill('等待回答');
  const before = requests.length;
  await evaluate('document.querySelector(".contract-questions form").requestSubmit(); document.querySelector(".contract-questions form").requestSubmit();');
  await until('document.querySelector(".contract-questions button").disabled && document.body.innerText.includes("正在查找相关约定")');
  for (let i = 0; i < 100 && !delayed; i++) await pause(50);
  if (!delayed || requests.length !== before + 1) throw new Error('Duplicate submission or no pending request');
  if (!(await evaluate('document.querySelector(".clear-questions").disabled'))) throw new Error('Pending history can be cleared');
  await upload('second.pdf');
  if (await evaluate('document.querySelector("#contract-question").value !== "" || document.querySelectorAll(".question-history > li").length !== 0')) throw new Error('Q&A history not reset');
  for (let i = 0; i < 100 && !aborted; i++) await pause(50);
  if (!aborted) throw new Error('Pending request was not aborted');
  delayed.end(JSON.stringify({ answer: 'OLD_ANSWER_MUST_NOT_RENDER' }));
  await submit('第二份合同押金什么时候退？');
  await until('Boolean(document.querySelector("[aria-label=合同问答结果]"))');
  if (requests.at(-1).doc_id !== 'b'.repeat(64) || await evaluate('document.body.innerText.includes("OLD_ANSWER_MUST_NOT_RENDER")')) throw new Error('Cross-document response leakage');
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  await evaluate('document.querySelectorAll(".contract-questions details").forEach(el => el.open = true)');
  if (!(await evaluate('(() => { const r = document.querySelector(".contract-questions").getBoundingClientRect(); return r.left >= 0 && r.right <= window.innerWidth + 1; })()'))) throw new Error('Q&A overflows mobile viewport');
  if (!(await evaluate('document.documentElement.scrollWidth <= 391'))) throw new Error('Page overflows mobile viewport');
  await evaluate('document.querySelector("[data-language-toggle]").click()');
  await until('document.documentElement.lang === "en"');
  await screenshot('qa-mobile.png');
  const beforeClear = requests.length;
  await evaluate('document.querySelector(".clear-questions").click()');
  await until('document.querySelectorAll(".question-history > li").length === 0');
  if (requests.length !== beforeClear || !(await evaluate('Boolean(document.querySelector("#contract-question"))'))) throw new Error('Clearing history sent a request or removed the contract');
  // Analysis lifecycle checks use only the same local mock server.
  async function changeRegion(value) {
    await evaluate(`(() => { const el = document.querySelector('.region-control select'); el.value = '${value}'; el.dispatchEvent(new Event('change', { bubbles: true })); })()`);
  }
  if (!(await evaluate('document.querySelector(".risk-panel .scope-hint").textContent.includes("contract-text issues only")'))) throw new Error('Unknown-region hint is wrong');
  await changeRegion('cn');
  await until('document.querySelector(".risk-panel .scope-hint").textContent.includes("Chinese mainland")');
  await changeRegion('us_il_urbana');
  await until('document.querySelector(".risk-panel .scope-hint").textContent.includes("Champaign")');
  for (const [mode, expected] of [['error', 'temporarily unavailable'], ['html', 'could not be read'], ['foreign', 'does not match']]) {
    analysisMode = mode;
    const before = analysisRequests.length;
    await evaluate('document.querySelector(".analysis-toolbar button").click()');
    await until(`document.querySelector('.risk-panel [role=alert]')?.textContent.includes('${expected}')`);
    if (await evaluate('Boolean(document.querySelector(".report-header")) || document.body.innerText.includes("FOREIGN_REPORT_MUST_NOT_RENDER")')) throw new Error('Failed analysis rendered a report');
    if (await evaluate('document.querySelector(".analysis-toolbar button").disabled')) throw new Error('Analysis retry is disabled');
  }
  for (const mode of Object.keys(malformedReports)) {
    analysisMode = mode;
    const before = analysisRequests.length;
    await evaluate('document.querySelector(".analysis-toolbar button").click()');
    for (let i = 0; i < 100 && analysisRequests.length === before; i++) await pause(50);
    if (analysisRequests.length !== before + 1) throw new Error(`Missing malformed report request: ${mode}`);
    await until('!document.querySelector(".analysis-toolbar button").disabled && document.querySelector(".risk-panel [role=alert]")?.textContent.includes("incomplete or invalid")');
    if (await evaluate('Boolean(document.querySelector(".report-header")) || document.querySelector(".analysis-toolbar button").disabled')) throw new Error(`Malformed report rendered or blocked retry: ${mode}`);
  }
  analysisMode = 'ok';
  await evaluate('document.querySelector(".analysis-toolbar button").click()');
  await until('document.querySelector(".report-summary")?.textContent.includes("ORIGINAL_SUMMARY")');
  if (await evaluate('Boolean(document.querySelector(".risk-panel script")) || Boolean(window.reportInjected)')) throw new Error('Report text interpreted as HTML');
  if (!(await evaluate('document.querySelector(".clause-quote").textContent === "Original contract clause." && document.querySelector(".source-text").textContent === "<script>window.reportInjected = true</script>"'))) throw new Error('Valid report content changed');
  if (analysisRequests.at(-1).doc_id !== 'b'.repeat(64) || analysisRequests.at(-1).jurisdiction !== 'us_il_urbana') throw new Error('Wrong analysis payload');
  const beforeAnalysisLanguage = analysisRequests.length;
  await evaluate('document.querySelector("[data-language-toggle]").click()');
  await until('document.documentElement.lang === "zh-CN"');
  if (!(await evaluate('document.querySelector(".report-summary")?.textContent.includes("ORIGINAL_SUMMARY")')) || analysisRequests.length !== beforeAnalysisLanguage) throw new Error('Language toggle changed analysis');
  await changeRegion('unknown');
  await until('!document.querySelector(".report-header")');
  analysisMode = 'pending';
  const beforeAnalysis = analysisRequests.length;
  await evaluate('(() => { const b = document.querySelector(".analysis-toolbar button"); b.click(); b.click(); })()');
  await until('document.querySelector(".analysis-toolbar button").disabled && document.querySelector(".region-control select").disabled');
  for (let i = 0; i < 100 && !delayedAnalysis; i++) await pause(50);
  if (!delayedAnalysis || analysisRequests.length !== beforeAnalysis + 1) throw new Error('Duplicate analysis request or missing pending request');
  await upload('third.pdf');
  for (let i = 0; i < 100 && !analysisAborted; i++) await pause(50);
  if (!analysisAborted) throw new Error('Pending analysis fetch was not aborted on file change');
  delayedAnalysis.end(JSON.stringify({ doc_id: 'b'.repeat(64), result: { ...analysisResult, summary: 'OLD_REPORT_MUST_NOT_RENDER' } }));
  await pause(100);
  if (await evaluate('Boolean(document.querySelector(".report-header")) || document.body.innerText.includes("OLD_REPORT_MUST_NOT_RENDER")')) throw new Error('Old analysis leaked into new document');
  analysisMode = 'empty';
  await evaluate('document.querySelector(".analysis-toolbar button").click()');
  await until('Boolean(document.querySelector(".report-header"))');
  if (await evaluate('document.querySelectorAll(".risk-card").length !== 0 || Boolean(document.querySelector(".risk-panel [role=alert]"))')) throw new Error('Valid zero-card report rejected');
  if (browserErrors.length) throw new Error('Browser errors: ' + browserErrors.join('\n'));
  await writeFile(path.join(out, 'checks.json'), JSON.stringify({ mode: 'local mock API; no model API calls', checks: ['16 malformed analysis payloads rejected without page failure; retry remains available', 'valid risk and law text preserved literally', 'analysis duplicate blocked', 'pending analysis aborted on file change', 'foreign analysis rejected', 'analysis HTML and 502 errors allow retry', 'analysis region hint and report reset', 'language toggle preserves original report', 'client 20 MiB limit with no upload request', 'HTML 413 readable', 'index 503 readable', 'incomplete upload response rejected', 'duplicate upload blocked', 'upload required', 'trimmed questions', 'whitespace rejected', 'two questions retained with independent API payloads', 'per-turn errors preserve earlier answers', 'clearing local history sends no request', 'document-scoped answer and sources', 'literal text rendering', '409/502/404 errors', 'foreign source rejected', 'blank answer rejected', 'invalid JSON', 'duplicate submit blocked', 'file change clears history and aborts pending fetch', 'new document ID sent', 'mobile width', 'home widths 320/390/768/1200', 'labeled file picker', 'English default UI', 'language preference survives reload', 'existing errors relocalize', 'unknown service detail preserved under an English fallback', 'language switch preserves answers and sends no request', 'suggestion only prefills and focuses without request'], requests, analysisRequests }, null, 2));
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

import { spawn } from 'node:child_process';
import { mkdir, mkdtemp, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { startDemo } from './demo.mjs';

const out = process.env.DEMO_UI_OUTPUT || await mkdtemp(path.join(tmpdir(), 'contract-replay-ui-'));
await mkdir(out, { recursive: true });
const server = await startDemo({ port: 0 });
const base = `http://127.0.0.1:${server.httpServer.address().port}`;
let browser;
let socket;
let counter = 0;
const waiting = new Map();
const errors = [];
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
function send(method, params = {}) {
  const id = ++counter;
  return new Promise((resolve, reject) => { waiting.set(id, { resolve, reject }); socket.send(JSON.stringify({ id, method, params })); });
}
async function evaluate(expression) {
  const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}
async function until(expression) {
  for (let i = 0; i < 150; i++) { if (await evaluate(expression)) return; await pause(100); }
  throw new Error('UI condition timed out: ' + expression);
}
async function capture(name, clip) {
  const result = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true, clip: { ...clip, scale: 1 } });
  await writeFile(path.join(out, name), Buffer.from(result.data, 'base64'));
}
async function question(value) {
  await evaluate(`(() => { const el = document.querySelector('#contract-question'); Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(el, ${JSON.stringify(value)}); el.dispatchEvent(new Event('input', {bubbles:true})); })()`);
  await evaluate('document.querySelector(".contract-questions form").requestSubmit()');
}

try {
  const profile = await mkdtemp(path.join(out, 'browser-profile-'));
  browser = spawn(process.env.EDGE_PATH || String.raw`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`, [
    '--headless', '--disable-gpu', '--disable-background-networking', '--disable-component-update', '--no-first-run',
    '--no-default-browser-check', '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank',
  ], { windowsHide: true, stdio: 'ignore' });
  let launchError;
  browser.on('error', error => { launchError = error; });
  let target;
  for (let i = 0; i < 100; i++) {
    if (launchError) throw launchError;
    try {
      const port = Number((await readFile(path.join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0]);
      if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Invalid owned-browser port');
      target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json(); break;
    } catch { await pause(100); }
  }
  if (!target) throw new Error('Edge did not start; set EDGE_PATH if needed.');
  socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { socket.addEventListener('open', resolve, { once: true }); socket.addEventListener('error', reject, { once: true }); });
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.method === 'Runtime.consoleAPICalled' && message.params.type === 'error') errors.push(message.params.args.map(arg => arg.value || arg.description).join(' '));
    if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.text);
    const pending = waiting.get(message.id);
    if (!pending) return;
    waiting.delete(message.id);
    if (message.error) pending.reject(new Error(JSON.stringify(message.error))); else pending.resolve(message.result);
  });
  await send('Page.enable');
  await send('Runtime.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: 1200, height: 1500, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: base });
  await until('Boolean(document.querySelector("[aria-label=回放演示说明]"))');
  if (!(await evaluate('document.body.innerText.includes("含已知解释偏差")'))) throw new Error('Missing replay limitation');
  const fixture = path.join(out, 'lease_en.pdf');
  await writeFile(fixture, Buffer.from(await (await fetch(base + '/demo/lease_en.pdf')).arrayBuffer()));
  const doc = await send('DOM.getDocument');
  const input = await send('DOM.querySelector', { nodeId: doc.root.nodeId, selector: 'input[type=file]' });
  await send('DOM.setFileInputFiles', { nodeId: input.nodeId, files: [fixture] });
  await evaluate('Array.from(document.querySelectorAll("button")).find(el => el.textContent === "上传").click()');
  await until('Boolean(document.querySelector("select"))');
  await evaluate('Array.from(document.querySelectorAll("button")).find(el => el.textContent === "分析风险").click()');
  await until('document.body.innerText.includes("此回放样例请先选择")');
  await evaluate('const el = document.querySelector("select"); el.value = "us_il_urbana"; el.dispatchEvent(new Event("change", {bubbles:true}));');
  await evaluate('Array.from(document.querySelectorAll("button")).find(el => el.textContent === "分析风险").click()');
  await until('document.querySelectorAll("section[aria-label=合同风险报告] article").length === 12');
  await capture('demo-overview.png', { x: 0, y: 0, width: 1200, height: 1230 });
  await question('其他问题');
  await until('document.querySelector(".contract-questions [role=alert]")?.textContent.includes("预设问题")');
  await question('押金多久退还？');
  await until('Boolean(document.querySelector("article[aria-label=合同问答结果]"))');
  if (!(await evaluate('document.querySelector(".contract-answer").textContent.startsWith("预设示例：")'))) throw new Error('Scripted answer not labeled');
  await evaluate('document.querySelectorAll(".contract-questions details").forEach(el => el.open = true)');
  const qaClip = await evaluate('(() => { const r = document.querySelector(".contract-questions").getBoundingClientRect(); return {x:Math.floor(r.left),y:Math.floor(r.top+scrollY),width:Math.ceil(r.width),height:Math.ceil(r.height)}; })()');
  await capture('demo-questions.png', qaClip);
  if (errors.length) throw new Error(errors.join('\n'));
  await writeFile(path.join(out, 'checks.json'), JSON.stringify({ mode: 'recorded analysis plus scripted Q&A; no model calls', checks: ['visible replay/limitations banner', 'fixture download and upload', 'region selection required', '12 recorded risk cards', 'unsupported question rejected', 'scripted answer labeled', 'expandable exact source chunks'], screenshots: ['demo-overview.png', 'demo-questions.png'] }, null, 2));
  console.log('PASS: actual replay UI, source excerpts and screenshots. No model calls.');
  console.log('Artifacts:', out);
} finally {
  try { if (socket?.readyState === WebSocket.OPEN) await send('Browser.close'); } catch {}
  socket?.close(); browser?.kill(); await server.close();
}

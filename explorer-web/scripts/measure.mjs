// Spike measurement orchestrator (TEA-902). Spawns the two-origin harness
// (pages on 8080, data on 8081 with CORS: genuinely cross-origin), drives
// Chromium via Playwright, and appends one JSON record per scenario to
// measurements/results.json.
//
//   node scripts/measure.mjs --dist dist --data-dir ../data/snapshot_sample \
//     --scenarios cold,warm,throttled,doc,heap --doc-slug <slug> --label sample-100
//
// Scenarios: cold, warm, throttled, doc, worst, bfcache, heap.

import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';

import { chromium } from 'playwright';

const PAGES_PORT = 8080;
const DATA_PORT = 8081;
const PAGES_ORIGIN = `http://127.0.0.1:${PAGES_PORT}`;

function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`);
  return i === -1 ? fallback : process.argv[i + 1];
}

const dist = arg('dist', 'dist');
const dataDir = arg('data-dir');
const scenarios = arg('scenarios', 'cold,warm,heap').split(',');
const docSlug = arg('doc-slug');
const worstSlug = arg('worst-slug');
const label = arg('label', 'unlabeled');
if (!dataDir) {
  console.error('measure: --data-dir is required');
  process.exit(1);
}

const results = [];
const record = (scenario, data) => {
  const rec = { label, scenario, ...data };
  results.push(rec);
  console.log(`\n=== ${scenario} ===`);
  console.log(JSON.stringify(rec, null, 2));
};

function spawnServer(args) {
  const child = spawn('node', ['scripts/serve-static.mjs', ...args], { stdio: 'inherit' });
  child.on('exit', (code) => {
    if (code !== null && code !== 0) console.error(`serve-static exited ${code}`);
  });
  return child;
}

async function waitForServer(origin) {
  for (let i = 0; i < 50; i++) {
    try {
      const res = await fetch(origin + '/', { method: 'HEAD' });
      if (res.status < 500) return;
    } catch {
      await new Promise((r) => setTimeout(r, 200));
    }
  }
  throw new Error(`server at ${origin} never came up`);
}

// Network byte accounting via CDP (works cross-origin, includes encoding).
async function trackNetwork(page) {
  const client = await page.context().newCDPSession(page);
  await client.send('Network.enable');
  const byRequest = new Map();
  const summary = { transferredBytes: 0, wasm: { url: '', transferredBytes: 0 }, requests: 0 };
  client.on('Network.responseReceived', (e) => {
    byRequest.set(e.requestId, e.response.url);
  });
  client.on('Network.loadingFinished', (e) => {
    const url = byRequest.get(e.requestId) ?? '';
    summary.transferredBytes += e.encodedDataLength;
    summary.requests += 1;
    if (/\.wasm(\?|$)/.test(url)) {
      summary.wasm.url = url;
      summary.wasm.transferredBytes += e.encodedDataLength;
    }
  });
  return { client, summary };
}

async function browseMetrics(page) {
  await page.waitForFunction(() => window.__ewMetrics && window.__ewMetrics.totalToFirstRenderMs > 0, undefined, {
    timeout: 180000,
  });
  const metrics = await page.evaluate(() => window.__ewMetrics);
  const wasmResource = await page.evaluate(() => {
    const entry = performance.getEntriesByType('resource').find((r) => r.name.includes('.wasm'));
    return entry ? { durationMs: entry.duration } : null;
  });
  return { ...metrics, wasmFetchMs: wasmResource?.durationMs ?? null };
}

async function docMetrics(page, slug, clickGate) {
  await page.goto(`${PAGES_ORIGIN}/doc/${slug}/`, { waitUntil: 'load' });
  if (clickGate) {
    await page.waitForSelector('#ew-doc-text button', { timeout: 30000 });
    await page.click('#ew-doc-text button');
  }
  await page.waitForFunction(() => window.__ewDocMetrics !== undefined, undefined, { timeout: 300000 });
  return page.evaluate(() => window.__ewDocMetrics);
}

const servers = [
  spawnServer(['--dir', dist, '--port', String(PAGES_PORT)]),
  spawnServer(['--dir', dataDir, '--port', String(DATA_PORT), '--cors']),
];

try {
  await waitForServer(PAGES_ORIGIN);
  await waitForServer(`http://127.0.0.1:${DATA_PORT}`);

  const browser = await chromium.launch();

  if (scenarios.includes('cold') || scenarios.includes('warm') || scenarios.includes('heap')) {
    const context = await browser.newContext();
    const page = await context.newPage();
    const net = await trackNetwork(page);
    await page.goto(`${PAGES_ORIGIN}/`, { waitUntil: 'load' });
    const cold = await browseMetrics(page);
    if (scenarios.includes('cold')) record('cold', { ...cold, network: net.summary });

    if (scenarios.includes('heap')) {
      const heap = await page.evaluate(() => performance.memory?.usedJSHeapSize ?? null);
      record('heap', { usedJSHeapSizeBytes: heap });
    }

    if (scenarios.includes('warm')) {
      await page.goto(`${PAGES_ORIGIN}/`, { waitUntil: 'load' });
      const warm = await browseMetrics(page);
      record('warm', warm);
    }
    await context.close();
  }

  if (scenarios.includes('throttled')) {
    const context = await browser.newContext();
    const page = await context.newPage();
    const net = await trackNetwork(page);
    await net.client.send('Emulation.setCPUThrottlingRate', { rate: 4 });
    await net.client.send('Network.emulateNetworkConditions', {
      offline: false,
      latency: 40,
      downloadThroughput: 8_000_000 / 8,
      uploadThroughput: 1_000_000 / 8,
    });
    await page.goto(`${PAGES_ORIGIN}/`, { waitUntil: 'load' });
    const metrics = await browseMetrics(page);
    record('throttled', { cpu: '4x', network: '~8Mbps/40ms', ...metrics, transferred: net.summary });
    await context.close();
  }

  if (scenarios.includes('doc') && docSlug) {
    const context = await browser.newContext();
    const page = await context.newPage();
    record('doc', { slug: docSlug, ...(await docMetrics(page, docSlug, false)) });
    await context.close();
  }

  if (scenarios.includes('worst') && worstSlug) {
    const context = await browser.newContext();
    const page = await context.newPage();
    const t0 = Date.now();
    const metrics = await docMetrics(page, worstSlug, true);
    record('worst', { slug: worstSlug, gateEngaged: true, wallMsFromNav: Date.now() - t0, ...metrics });
    await context.close();
  }

  if (scenarios.includes('bfcache')) {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.goto(`${PAGES_ORIGIN}/`, { waitUntil: 'load' });
    await browseMetrics(page);
    await page.locator('#ew-rows tr a').first().click();
    await page.waitForURL('**/doc/**');
    const tBack = Date.now();
    await page.goBack();
    await page.waitForSelector('#ew-rows tr', { timeout: 180000 });
    const backMs = Date.now() - tBack;
    const notRestored = await page.evaluate(() => {
      const nav = performance.getEntriesByType('navigation')[0];
      return nav && 'notRestoredReasons' in nav ? JSON.stringify(nav.notRestoredReasons) : 'unsupported';
    });
    record('bfcache', { backNavMs: backMs, notRestoredReasons: notRestored });
    await context.close();
  }

  await browser.close();
} finally {
  for (const server of servers) server.kill();
}

const outDir = 'measurements';
mkdirSync(outDir, { recursive: true });
const outFile = path.join(outDir, 'results.json');
const existing = existsSync(outFile) ? JSON.parse(readFileSync(outFile, 'utf8')) : [];
existing.push({ ranAt: new Date().toISOString(), label, records: results });
writeFileSync(outFile, JSON.stringify(existing, null, 2));
console.log(`\nmeasure: ${results.length} scenario record(s) appended to ${outFile}`);

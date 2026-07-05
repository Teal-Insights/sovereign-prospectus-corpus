// Browser smoke for the S3 explorer against a SERVED build (two origins,
// mirroring the measurement harness: pages on one port, snapshot data with
// CORS on another; serve-static serves a single directory at its root, so a
// /data path prefix does not exist). From explorer-web/:
//
//   SNAPSHOT_DIR=tests/fixtures/snapshot PUBLIC_DATA_BASE_URL=http://127.0.0.1:8081 npx astro build
//   node scripts/serve-static.mjs --dir dist --port 8080 &
//   node scripts/serve-static.mjs --dir tests/fixtures/snapshot --port 8081 --cors &
//   SMOKE_BASE=http://127.0.0.1:8080 node scripts/smoke.mjs
//
// Scenario coverage tracks the S3 plan: filters + URL passthrough, history
// discipline (clamp via replaceState), interplay override, doc search with
// live-region announcements, segmented rendering, the 5 MB gate with ?q=,
// the no-Highlight-API fallback, and an axe pass.
import { AxeBuilder } from '@axe-core/playwright';
import { chromium } from 'playwright';

const BASE = process.env.SMOKE_BASE ?? 'http://127.0.0.1:8080';
const results = [];
const check = (name, ok, detail = '') => {
  results.push({ name, ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${detail ? ` :: ${detail}` : ''}`);
};

const browser = await chromium.launch();
const page = await browser.newPage();
page.on('console', (m) => {
  if (m.type() === 'error') console.log('CONSOLE ERROR:', m.text());
});
page.on('pageerror', (e) => check('no page errors', false, e.message));

const browseReady = () =>
  page.waitForFunction(() => (window.__ewMetrics?.rowsRendered ?? 0) > 0, null, { timeout: 120000 });
const docReady = () =>
  page.waitForFunction(() => window.__ewDocMetrics !== undefined, null, { timeout: 120000 });

// ---- (a) filters, URL passthrough ----
await page.goto(`${BASE}/?utm=x`, { waitUntil: 'load' });
await browseReady();
const status1 = await page.textContent('#ew-status');
check('status line matrix', /documents match, newest first/.test(status1), status1.trim());
check('marginal hidden sentences', status1.includes('would add'), '');

const firstCountry = await page.locator('#ew-filter-country-select option').nth(1).getAttribute('value');
await page.selectOption('#ew-filter-country-select', firstCountry);
await page.waitForFunction(() => new URLSearchParams(location.search).has('country'));
check('country chip in URL', true, page.url());
check('unknown param survives interaction', new URL(page.url()).searchParams.get('utm') === 'x');
check('chip rendered', (await page.locator('#ew-filter-country-chips .ew-chip').count()) === 1);
const metrics = await page.evaluate(() => window.__ewMetrics);
check('metrics populated', Boolean(metrics && metrics.bundleName && metrics.totalToFirstRenderMs > 0));

// ---- (b) history discipline ----
await page.goBack();
await page.waitForFunction(() => !new URLSearchParams(location.search).has('country'));
check('back restores unfiltered state', (await page.locator('#ew-filter-country-chips .ew-chip').count()) === 0);
await page.goForward();
await page.waitForFunction(() => new URLSearchParams(location.search).has('country'));
check('forward restores the chip', (await page.locator('#ew-filter-country-chips .ew-chip').count()) === 1);
await page.goBack();
await page.waitForFunction(() => !new URLSearchParams(location.search).has('country'));

await page.goto(`${BASE}/?page=99`, { waitUntil: 'load' });
const lenAfterNav = await page.evaluate(() => history.length);
await browseReady();
await page.waitForFunction(() => !location.search.includes('page=99'));
const lenAfterClamp = await page.evaluate(() => history.length);
check('page clamp uses replaceState (no history growth)', lenAfterNav === lenAfterClamp, `${lenAfterNav} -> ${lenAfterClamp}`);

// zero results must still explain what the toggles hide (Poland scenario:
// FIN is one sovereign High-income doc, hidden by the default exclusion).
// browseReady() gates on rows > 0, which a zero-result page never reaches.
await page.goto(`${BASE}/?country=FIN`, { waitUntil: 'load' });
await page.waitForFunction(
  () => document.getElementById('ew-status')?.textContent?.includes('No documents match'),
  null,
  { timeout: 120000 }
);
const zeroStatus = await page.textContent('#ew-status');
check(
  'zero results keep the would-add sentences',
  zeroStatus.includes('No documents match') && zeroStatus.includes('would add'),
  zeroStatus.trim()
);

await page.goto(`${BASE}/?country=ZZ`, { waitUntil: 'load' });
await page.waitForSelector('#ew-browse-notices .ew-notice');
check('dropped-param notice', (await page.textContent('#ew-browse-notices')).includes('no longer valid'));
check('invalid value removed from URL', !page.url().includes('ZZ'), page.url());

// ---- (c) interplay override ----
await page.goto(`${BASE}/`, { waitUntil: 'load' });
await browseReady();
await page.selectOption('#ew-filter-income-select', 'Unknown');
await page.waitForFunction(() => new URLSearchParams(location.search).has('income'));
check('hi toggle disabled under income selection', await page.locator('#ew-hi-toggle').isDisabled());
check('hint visible', (await page.locator('#ew-hi-hint.ew-visible').count()) === 1);
const statusNoHi = await page.textContent('#ew-status');
check('no override sentence without High income', !statusNoHi.includes('income filter'), statusNoHi.trim());
await page.selectOption('#ew-filter-income-select', 'High income');
await page.waitForFunction(() =>
  document.getElementById('ew-status')?.textContent?.includes('included by the income filter')
);
check('override sentence with High income selected', true);

// ---- (d) doc page: TOC jump focus, search, segments ----
await page.goto(`${BASE}/doc/synthetic-large/`, { waitUntil: 'load' });
await docReady();
check('segmented mode', /Segment 1 of \d+/.test(await page.textContent('#ew-seg-label')));
check('provenance notice visible', (await page.textContent('body')).includes('Text is machine-converted'));
check('seg prev starts aria-disabled', (await page.getAttribute('#ew-seg-prev', 'aria-disabled')) === 'true');
await page.click('#ew-seg-next');
await page.waitForFunction(() => document.getElementById('ew-seg-label')?.textContent?.includes('Segment 2'), null, { timeout: 10000 });
check('segment next button works', true);
await page.click('#ew-seg-prev');
await page.waitForFunction(() => document.getElementById('ew-seg-label')?.textContent?.includes('Segment 1'), null, { timeout: 10000 });
check('segment prev button works', true);
await page.locator('#ew-doc-toc-details summary').click();
await page.locator('#ew-doc-toc button').last().click();
await page.waitForFunction(() => window.scrollY > 0);
check('toc jump scrolls', true, `scrollY>0`);
check('toc jump focuses text', (await page.evaluate(() => document.activeElement?.id)) === 'ew-doc-text');
check('toc jump crossed segments', !/Segment 1 of/.test(await page.textContent('#ew-seg-label')));
await page.focus('#ew-doc-search-input');
await page.keyboard.type('## Sect');
await page.waitForFunction(() => /matches/.test(document.getElementById('ew-doc-search-count')?.textContent ?? ''), null, { timeout: 10000 });
check('typing keeps focus in the input', (await page.evaluate(() => document.activeElement?.id)) === 'ew-doc-search-input');
await page.keyboard.type('ion');
await page.waitForFunction(
  () => (document.getElementById('ew-doc-search-count')?.textContent ?? '').includes('"## Section"'),
  null,
  { timeout: 10000 }
);
check('continued typing lands in the query', (await page.inputValue('#ew-doc-search-input')) === '## Section');
await page.click('#ew-doc-search-next'); // first activation jumps to match 1
await page.waitForFunction(() => (document.getElementById('ew-doc-live')?.textContent ?? '').includes('Match 1 of 8'), null, { timeout: 10000 });
check('first Next goes to match 1 with snippet announced', true, await page.evaluate(() => document.getElementById('ew-doc-live')?.textContent));
check('visible position label', (await page.textContent('#ew-doc-search-pos')).includes('Match 1 of 8'));
await page.click('#ew-doc-search-next');
await page.waitForFunction(() => (document.getElementById('ew-doc-live')?.textContent ?? '').includes('Match 2 of 8'), null, { timeout: 10000 });
check('match navigation advances', true);
await page.focus('#ew-doc-search-input');
await page.keyboard.press('Enter');
await page.waitForFunction(() => (document.getElementById('ew-doc-live')?.textContent ?? '').includes('Match 3 of 8'), null, { timeout: 10000 });
check('Enter advances to the next match', true);
const tocCounts = await page.evaluate(
  () => [...document.querySelectorAll('#ew-doc-toc .ew-toc-count')].filter((e) => e.textContent !== '').length
);
check('per-section counts rendered', tocCounts === 8, `counts=${tocCounts}`);
const segPainted = await page.evaluate(() => (CSS.highlights.get('ew-match-current')?.size ?? 0) === 1);
check('current match painted', segPainted);

// ---- (e) gate: ?q= never bypasses consent ----
let textFetches = 0;
await page.route('**/text/synthetic-gate.json*', (route) => {
  textFetches++;
  return route.continue();
});
await page.goto(`${BASE}/doc/synthetic-gate/?q=gate`, { waitUntil: 'load' });
await page.waitForSelector('#ew-doc-text button');
await page.waitForTimeout(400);
check('gate shows without fetching', textFetches === 0, `fetches=${textFetches}`);
await page.click('#ew-doc-text button');
await docReady();
await page.waitForFunction(() => (document.getElementById('ew-doc-search-count')?.textContent ?? '').includes('match'), null, { timeout: 10000 });
check('q runs after gate click', textFetches === 1, await page.textContent('#ew-doc-search-count'));
await page.unroute('**/text/synthetic-gate.json*');

// ---- (f) no-Highlight-API fallback ----
const fallbackPage = await browser.newPage();
await fallbackPage.addInitScript(() => {
  delete CSS.highlights;
});
await fallbackPage.goto(`${BASE}/doc/synthetic-astral/`, { waitUntil: 'load' });
await fallbackPage.waitForFunction(() => window.__ewDocMetrics !== undefined, null, { timeout: 120000 });
const supportNoteShown = await fallbackPage.evaluate(
  () => document.getElementById('ew-doc-notices')?.textContent?.includes('newer browser') ?? false
);
check('support note shown before typing', supportNoteShown);
await fallbackPage.fill('#ew-doc-search-input', 'Heading');
await fallbackPage.waitForFunction(() => /2 matches/.test(document.getElementById('ew-doc-search-count')?.textContent ?? ''), null, { timeout: 10000 });
await fallbackPage.click('#ew-doc-search-next'); // first activation -> match 1
await fallbackPage.waitForFunction(() => (document.getElementById('ew-doc-live')?.textContent ?? '').includes('Match 1 of 2'), null, { timeout: 10000 });
await fallbackPage.click('#ew-doc-search-next');
await fallbackPage.waitForFunction(() => (document.getElementById('ew-doc-live')?.textContent ?? '').includes('Match 2 of 2'), null, { timeout: 10000 });
check('counts and navigation work without Highlight API', true);
await fallbackPage.close();

// ---- (g) axe: zero serious/critical (axe needs a context-created page) ----
const axeContext = await browser.newContext();
const axePage = await axeContext.newPage();
await axePage.goto(`${BASE}/`, { waitUntil: 'load' });
await axePage.waitForFunction(() => (window.__ewMetrics?.rowsRendered ?? 0) > 0, null, { timeout: 120000 });
const axeBrowse = await new AxeBuilder({ page: axePage }).options({ rules: { 'target-size': { enabled: true } } }).analyze();
const badBrowse = axeBrowse.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
check('axe browse: no serious/critical', badBrowse.length === 0, JSON.stringify(badBrowse.map((v) => v.id)));

// stateful run: chips + income override hint + notices in the DOM
const firstAxeCountry = await axePage.locator('#ew-filter-country-select option').nth(1).getAttribute('value');
await axePage.selectOption('#ew-filter-country-select', firstAxeCountry);
await axePage.selectOption('#ew-filter-income-select', 'High income');
await axePage.waitForFunction(() => document.querySelectorAll('.ew-chip').length === 2);
const axeStateful = await new AxeBuilder({ page: axePage }).options({ rules: { 'target-size': { enabled: true } } }).analyze();
const badStateful = axeStateful.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
check('axe browse with chips/override: no serious/critical', badStateful.length === 0, JSON.stringify(badStateful.map((v) => v.id)));

await axePage.goto(`${BASE}/doc/synthetic-large/`, { waitUntil: 'load' });
await axePage.waitForFunction(() => window.__ewDocMetrics !== undefined, null, { timeout: 120000 });
const axeDoc = await new AxeBuilder({ page: axePage }).analyze();
const badDoc = axeDoc.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
check('axe doc: no serious/critical', badDoc.length === 0, JSON.stringify(badDoc.map((v) => v.id)));
await axeContext.close();

await browser.close();
const failed = results.filter((r) => !r.ok);
console.log(failed.length ? `SMOKE FAILED: ${failed.length}` : 'SMOKE OK');
process.exit(failed.length ? 1 : 0);

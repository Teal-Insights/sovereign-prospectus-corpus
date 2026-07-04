// Dev smoke for the browse flow. Run from explorer-web/ with `npm run dev`
// already serving (default port 4321) against a snapshot:
//   node scripts/smoke.mjs
import { chromium } from 'playwright';

const BASE = process.env.SMOKE_BASE ?? 'http://localhost:4321';
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

await page.goto(`${BASE}/`, { waitUntil: 'load' });
await page.waitForSelector('#ew-rows tr', { timeout: 120000 });

const status1 = await page.textContent('#ew-status');
check('sovereign default status', /Showing [\d,]+ sovereign documents\./.test(status1), status1.trim());

const rows1 = await page.locator('#ew-rows tr').count();
check('rows rendered', rows1 > 0, `rows=${rows1}`);

const metrics = await page.evaluate(() => window.__ewMetrics);
check('metrics populated', Boolean(metrics && metrics.bundleName && metrics.firstQueryMs > 0), JSON.stringify(metrics));

// Scope toggle
const toggleText = await page.textContent('#ew-scope-toggle-text');
check('toggle label live counts', /Include [\d,]+ non-sovereign or unverified/.test(toggleText), toggleText.trim());
await page.check('#ew-scope-toggle');
await page.waitForFunction(() => new URLSearchParams(location.search).get('scope') === 'all');
check('scope in URL', page.url().includes('scope=all'), page.url());
await page.uncheck('#ew-scope-toggle');
await page.waitForFunction(() => new URLSearchParams(location.search).get('scope') === null);

// Country filter
const firstCountry = await page.locator('#ew-filter-country option').nth(1).getAttribute('value');
await page.selectOption('#ew-filter-country', firstCountry);
await page.waitForFunction(() => document.querySelector('#ew-status')?.textContent?.includes('match the current filters'));
check('country filter narrows', true, (await page.textContent('#ew-status')).trim());
check('country in URL', page.url().includes('country='), page.url());

// Navigate to a doc page and back
await page.locator('#ew-rows tr a').first().click();
await page.waitForURL('**/doc/**');
check('doc page navigated', page.url().includes('/doc/'), page.url());
const bodyText = await page.textContent('body');
check('doc provenance visible', bodyText.includes('Text is machine-converted') || bodyText.includes('No text available'));
await page.waitForFunction(
  () => window.__ewDocMetrics !== undefined || document.querySelector('#ew-doc-text button') !== null || document.querySelector('#ew-doc-text') === null,
  { timeout: 60000 }
);
await page.goBack();
await page.waitForSelector('#ew-rows tr', { timeout: 120000 });
check('back returns with state', page.url().includes('country='), page.url());

// Pagination
await page.selectOption('#ew-filter-country', '');
await page.waitForFunction(() => document.querySelector('#ew-status')?.textContent?.includes('Page 1'));
await page.click('#ew-next');
await page.waitForFunction(() => document.querySelector('#ew-status')?.textContent?.includes('Page 2'));
check('pagination next', true, (await page.textContent('#ew-status')).trim());

await browser.close();
const failed = results.filter((r) => !r.ok);
console.log(failed.length ? `SMOKE FAILED: ${failed.length}` : 'SMOKE OK');
process.exit(failed.length ? 1 : 0);

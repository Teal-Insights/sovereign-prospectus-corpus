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
//
// Optional scenario (h), guarded by SMOKE_EXT_BASE (TEA-932): proves the
// parquet extension loads from the self-host mirror with extensions.duckdb.org
// blocked. It needs a build made WITH PUBLIC_EXTENSION_BASE_URL=$SMOKE_EXT_BASE
// and an extension server at that origin serving the mirrored
// <core-version>/<wasm-platform>/parquet.duckdb_extension.wasm layout, e.g.:
//
//   SNAPSHOT_DIR=tests/fixtures/snapshot PUBLIC_DATA_BASE_URL=http://127.0.0.1:8081 \
//     PUBLIC_EXTENSION_BASE_URL=http://127.0.0.1:8082 npx astro build
//   node scripts/serve-static.mjs --dir <ext-mirror-dir> --port 8082 --cors &
//   SMOKE_BASE=http://127.0.0.1:8080 SMOKE_EXT_BASE=http://127.0.0.1:8082 node scripts/smoke.mjs
import { AxeBuilder } from "@axe-core/playwright";
import { readFile } from "node:fs/promises";
import { chromium } from "playwright";

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:8080";
const results = [];
const check = (name, ok, detail = "") => {
  results.push({ name, ok, detail });
  console.log(
    `${ok ? "PASS" : "FAIL"} ${name}${detail ? ` :: ${detail}` : ""}`,
  );
};

function parseCsv(csv) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < csv.length; i++) {
    const char = csv[i];
    if (quoted) {
      if (char === '"' && csv[i + 1] === '"') {
        field += '"';
        i++;
      } else if (char === '"') {
        quoted = false;
      } else {
        field += char;
      }
    } else if (char === '"') {
      quoted = true;
    } else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\r" && csv[i + 1] === "\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
      i++;
    } else if (char === "\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else {
      field += char;
    }
  }
  if (field || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  return rows;
}

const browser = await chromium.launch();
const page = await browser.newPage();
page.on("console", (m) => {
  if (m.type() === "error") console.log("CONSOLE ERROR:", m.text());
});
page.on("pageerror", (e) => check("no page errors", false, e.message));

const browseReady = () =>
  page.waitForFunction(
    () => (window.__ewMetrics?.rowsRendered ?? 0) > 0,
    null,
    { timeout: 120000 },
  );
const docReady = () =>
  page.waitForFunction(() => window.__ewDocMetrics !== undefined, null, {
    timeout: 120000,
  });

// ---- (a) filters, URL passthrough ----
await page.goto(`${BASE}/?utm=x`, { waitUntil: "load" });
await browseReady();
const status1 = await page.textContent("#ew-status");
check(
  "status line matrix",
  /documents match, newest first/.test(status1),
  status1.trim(),
);
check("marginal hidden sentences", status1.includes("would add"), "");

const firstCountryOption = page
  .locator("#ew-filter-country-select option")
  .nth(1);
const firstCountry = await firstCountryOption.getAttribute("value");
const firstCountryLabel = (
  (await firstCountryOption.textContent()) ?? ""
).trim();
await page.selectOption("#ew-filter-country-select", firstCountry);
await page.waitForFunction(() =>
  new URLSearchParams(location.search).has("country"),
);
check("country chip in URL", true, page.url());
check(
  "unknown param survives interaction",
  new URL(page.url()).searchParams.get("utm") === "x",
);
check(
  "chip rendered",
  (await page.locator("#ew-filter-country-chips .ew-chip").count()) === 1,
);

// The export query must use the current filter state, not the visible page.
// Capture the real Blob download and inspect the generated file.
await page.waitForFunction(
  () => !document.getElementById("ew-export")?.disabled,
);
const [exportDownload] = await Promise.all([
  page.waitForEvent("download"),
  page.click("#ew-export"),
]);
const exportFailure = await exportDownload.failure();
check(
  "export: Blob download completes",
  exportFailure === null,
  exportFailure ?? "",
);
const exportPath = await exportDownload.path();
const exportCsv = exportPath === null ? "" : await readFile(exportPath, "utf8");
check("export: download path is available", exportPath !== null);
check(
  "export: file starts with a UTF-8 BOM (Excel non-ASCII fidelity, #120)",
  exportCsv.startsWith("\ufeff"),
  JSON.stringify(exportCsv.slice(0, 1)),
);
const exportRows = parseCsv(exportCsv.replace(/^\ufeff/, ""));
const expectedExportHeader =
  "publication_date,issuer,display_name,title,raw_title,country,region,income_group,doc_type,source,is_sovereign,document_url,filing_url";
check(
  "export: CSV header is correct",
  exportRows[0]?.join(",") === expectedExportHeader,
  exportRows[0]?.join(","),
);
const exportedDocuments = exportRows.slice(1);
check(
  "export: filtered CSV contains rows",
  exportedDocuments.length > 0,
  `rows=${exportedDocuments.length}`,
);
check(
  "export: every row honors the selected country",
  exportedDocuments.every((row) => row[5] === firstCountryLabel),
  `country=${firstCountryLabel}`,
);
const snapshotDate = await page
  .locator("body")
  .getAttribute("data-build-snapshot-date");
check(
  "export: filename uses the build snapshot date",
  exportDownload.suggestedFilename() ===
    `prospectus-explorer-export-${snapshotDate}.csv`,
  exportDownload.suggestedFilename(),
);
const metrics = await page.evaluate(() => window.__ewMetrics);
check(
  "metrics populated",
  Boolean(metrics && metrics.bundleName && metrics.totalToFirstRenderMs > 0),
);

// ---- (b) history discipline ----
await page.goBack();
await page.waitForFunction(
  () => !new URLSearchParams(location.search).has("country"),
);
check(
  "back restores unfiltered state",
  (await page.locator("#ew-filter-country-chips .ew-chip").count()) === 0,
);
await page.goForward();
await page.waitForFunction(() =>
  new URLSearchParams(location.search).has("country"),
);
check(
  "forward restores the chip",
  (await page.locator("#ew-filter-country-chips .ew-chip").count()) === 1,
);
await page.goBack();
await page.waitForFunction(
  () => !new URLSearchParams(location.search).has("country"),
);

await page.goto(`${BASE}/?page=99`, { waitUntil: "load" });
const lenAfterNav = await page.evaluate(() => history.length);
await browseReady();
await page.waitForFunction(() => !location.search.includes("page=99"));
const lenAfterClamp = await page.evaluate(() => history.length);
check(
  "page clamp uses replaceState (no history growth)",
  lenAfterNav === lenAfterClamp,
  `${lenAfterNav} -> ${lenAfterClamp}`,
);

// zero results must still give a recovery hint.
// browseReady() gates on rows > 0, which a zero-result page never reaches.
await page.goto(
  `${BASE}/?country=FIN&income=${encodeURIComponent("Lower middle income")}`,
  { waitUntil: "load" },
);
await page.waitForFunction(
  () =>
    document
      .getElementById("ew-status")
      ?.textContent?.includes("No documents match"),
  null,
  { timeout: 120000 },
);
const zeroStatus = await page.textContent("#ew-status");
check(
  "zero results show recovery copy",
  zeroStatus.includes("No documents match") &&
    zeroStatus.includes("Remove a filter to widen the results"),
  zeroStatus.trim(),
);

await page.goto(`${BASE}/?country=ZZ`, { waitUntil: "load" });
await page.waitForSelector("#ew-browse-notices .ew-notice");
check(
  "dropped-param notice",
  (await page.textContent("#ew-browse-notices")).includes("no longer valid"),
);
check("invalid value removed from URL", !page.url().includes("ZZ"), page.url());

// ---- (c) interplay override ----
await page.goto(`${BASE}/`, { waitUntil: "load" });
await browseReady();
await page.selectOption("#ew-filter-income-select", "Unknown");
await page.waitForFunction(() =>
  new URLSearchParams(location.search).has("income"),
);
check(
  "hi toggle disabled under income selection",
  await page.locator("#ew-hi-toggle").isDisabled(),
);
check(
  "hint visible",
  (await page.locator("#ew-hi-hint.ew-visible").count()) === 1,
);
const statusNoHi = await page.textContent("#ew-status");
check(
  "no override sentence without High income",
  !statusNoHi.includes("income filter"),
  statusNoHi.trim(),
);
await page.selectOption("#ew-filter-income-select", "High income");
await page.waitForFunction(() =>
  document
    .getElementById("ew-status")
    ?.textContent?.includes("included by the income filter"),
);
check("override sentence with High income selected", true);

await page.goto(`${BASE}/`, { waitUntil: "load" });
await browseReady();
await page.selectOption("#ew-filter-country-select", "FIN");
await page.waitForFunction(() =>
  document
    .getElementById("ew-status")
    ?.textContent?.includes("because their countries are selected"),
);
check(
  "country override rows appear",
  (await page.locator("#ew-rows tr").count()) > 0,
);
check(
  "hi toggle disabled under country selection",
  await page.locator("#ew-hi-toggle").isDisabled(),
);
check(
  "country override hint visible",
  ((await page.textContent("#ew-hi-hint")) ?? "").includes(
    "Overridden by the country selection.",
  ),
);
const statusCountryHi = await page.textContent("#ew-status");
check(
  "country override status explains high-income inclusion",
  statusCountryHi.includes("because their countries are selected"),
  statusCountryHi.trim(),
);

// ---- (d) doc page: TOC jump focus, search, segments ----
await page.goto(`${BASE}/doc/synthetic-large/`, { waitUntil: "load" });
await docReady();
check(
  "segmented mode",
  /Segment 1 of \d+/.test(await page.textContent("#ew-seg-label")),
);
check(
  "provenance notice visible",
  (await page.textContent("body")).includes("Text is machine-converted"),
);
check(
  "seg prev starts aria-disabled",
  (await page.getAttribute("#ew-seg-prev", "aria-disabled")) === "true",
);
await page.click("#ew-seg-next");
await page.waitForFunction(
  () =>
    document.getElementById("ew-seg-label")?.textContent?.includes("Segment 2"),
  null,
  { timeout: 10000 },
);
check("segment next button works", true);
await page.click("#ew-seg-prev");
await page.waitForFunction(
  () =>
    document.getElementById("ew-seg-label")?.textContent?.includes("Segment 1"),
  null,
  { timeout: 10000 },
);
check("segment prev button works", true);
await page.locator("#ew-doc-toc-details summary").click();
await page.locator("#ew-doc-toc button").last().click();
await page.waitForFunction(() => window.scrollY > 0);
check("toc jump scrolls", true, `scrollY>0`);
check(
  "toc jump focuses text",
  (await page.evaluate(() => document.activeElement?.id)) === "ew-doc-text",
);
check(
  "toc jump crossed segments",
  !/Segment 1 of/.test(await page.textContent("#ew-seg-label")),
);
await page.focus("#ew-doc-search-input");
await page.keyboard.type("## Sect");
await page.waitForFunction(
  () =>
    /matches/.test(
      document.getElementById("ew-doc-search-count")?.textContent ?? "",
    ),
  null,
  { timeout: 10000 },
);
check(
  "typing keeps focus in the input",
  (await page.evaluate(() => document.activeElement?.id)) ===
    "ew-doc-search-input",
);
await page.keyboard.type("ion");
await page.waitForFunction(
  () =>
    (
      document.getElementById("ew-doc-search-count")?.textContent ?? ""
    ).includes('"## Section"'),
  null,
  { timeout: 10000 },
);
check(
  "continued typing lands in the query",
  (await page.inputValue("#ew-doc-search-input")) === "## Section",
);
await page.click("#ew-doc-search-next"); // first activation jumps to match 1
await page.waitForFunction(
  () =>
    (document.getElementById("ew-doc-live")?.textContent ?? "").includes(
      "Match 1 of 8",
    ),
  null,
  { timeout: 10000 },
);
check(
  "first Next goes to match 1 with snippet announced",
  true,
  await page.evaluate(
    () => document.getElementById("ew-doc-live")?.textContent,
  ),
);
check(
  "visible position label",
  (await page.textContent("#ew-doc-search-pos")).includes("Match 1 of 8"),
);
await page.click("#ew-doc-search-next");
await page.waitForFunction(
  () =>
    (document.getElementById("ew-doc-live")?.textContent ?? "").includes(
      "Match 2 of 8",
    ),
  null,
  { timeout: 10000 },
);
check("match navigation advances", true);
await page.focus("#ew-doc-search-input");
await page.keyboard.press("Enter");
await page.waitForFunction(
  () =>
    (document.getElementById("ew-doc-live")?.textContent ?? "").includes(
      "Match 3 of 8",
    ),
  null,
  { timeout: 10000 },
);
check("Enter advances to the next match", true);
const tocCounts = await page.evaluate(
  () =>
    [...document.querySelectorAll("#ew-doc-toc .ew-toc-count")].filter(
      (e) => e.textContent !== "",
    ).length,
);
check("per-section counts rendered", tocCounts === 8, `counts=${tocCounts}`);
const segPainted = await page.evaluate(
  () => (CSS.highlights.get("ew-match-current")?.size ?? 0) === 1,
);
check("current match painted", segPainted);

// ---- (e) gate: ?q= never bypasses consent ----
let textFetches = 0;
await page.route("**/text/synthetic-gate.json*", (route) => {
  textFetches++;
  return route.continue();
});
await page.goto(`${BASE}/doc/synthetic-gate/?q=gate`, { waitUntil: "load" });
await page.waitForSelector("#ew-doc-text button");
await page.waitForTimeout(400);
check(
  "gate shows without fetching",
  textFetches === 0,
  `fetches=${textFetches}`,
);
await page.click("#ew-doc-text button");
await docReady();
await page.waitForFunction(
  () =>
    (
      document.getElementById("ew-doc-search-count")?.textContent ?? ""
    ).includes("match"),
  null,
  { timeout: 10000 },
);
check(
  "q runs after gate click",
  textFetches === 1,
  await page.textContent("#ew-doc-search-count"),
);
await page.unroute("**/text/synthetic-gate.json*");

// ---- (f) no-Highlight-API fallback ----
const fallbackPage = await browser.newPage();
await fallbackPage.addInitScript(() => {
  delete CSS.highlights;
});
await fallbackPage.goto(`${BASE}/doc/synthetic-astral/`, { waitUntil: "load" });
await fallbackPage.waitForFunction(
  () => window.__ewDocMetrics !== undefined,
  null,
  { timeout: 120000 },
);
const supportNoteShown = await fallbackPage.evaluate(
  () =>
    document
      .getElementById("ew-doc-notices")
      ?.textContent?.includes("newer browser") ?? false,
);
check("support note shown before typing", supportNoteShown);
await fallbackPage.fill("#ew-doc-search-input", "Heading");
await fallbackPage.waitForFunction(
  () =>
    /2 matches/.test(
      document.getElementById("ew-doc-search-count")?.textContent ?? "",
    ),
  null,
  { timeout: 10000 },
);
await fallbackPage.click("#ew-doc-search-next"); // first activation -> match 1
await fallbackPage.waitForFunction(
  () =>
    (document.getElementById("ew-doc-live")?.textContent ?? "").includes(
      "Match 1 of 2",
    ),
  null,
  { timeout: 10000 },
);
await fallbackPage.click("#ew-doc-search-next");
await fallbackPage.waitForFunction(
  () =>
    (document.getElementById("ew-doc-live")?.textContent ?? "").includes(
      "Match 2 of 2",
    ),
  null,
  { timeout: 10000 },
);
check("counts and navigation work without Highlight API", true);
await fallbackPage.close();

// ---- (g) axe: zero serious/critical (axe needs a context-created page) ----
const axeContext = await browser.newContext();
const axePage = await axeContext.newPage();
await axePage.goto(`${BASE}/`, { waitUntil: "load" });
await axePage.waitForFunction(
  () => (window.__ewMetrics?.rowsRendered ?? 0) > 0,
  null,
  { timeout: 120000 },
);
const axeBrowse = await new AxeBuilder({ page: axePage })
  .options({ rules: { "target-size": { enabled: true } } })
  .analyze();
const badBrowse = axeBrowse.violations.filter(
  (v) => v.impact === "serious" || v.impact === "critical",
);
check(
  "axe browse: no serious/critical",
  badBrowse.length === 0,
  JSON.stringify(badBrowse.map((v) => v.id)),
);

// stateful run: chips + income override hint + notices in the DOM
const firstAxeCountry = await axePage
  .locator("#ew-filter-country-select option")
  .nth(1)
  .getAttribute("value");
await axePage.selectOption("#ew-filter-country-select", firstAxeCountry);
await axePage.selectOption("#ew-filter-income-select", "High income");
await axePage.waitForFunction(
  () => document.querySelectorAll(".ew-chip").length === 2,
);
const axeStateful = await new AxeBuilder({ page: axePage })
  .options({ rules: { "target-size": { enabled: true } } })
  .analyze();
const badStateful = axeStateful.violations.filter(
  (v) => v.impact === "serious" || v.impact === "critical",
);
check(
  "axe browse with chips/override: no serious/critical",
  badStateful.length === 0,
  JSON.stringify(badStateful.map((v) => v.id)),
);

await axePage.goto(`${BASE}/doc/synthetic-large/`, { waitUntil: "load" });
await axePage.waitForFunction(() => window.__ewDocMetrics !== undefined, null, {
  timeout: 120000,
});
const axeDoc = await new AxeBuilder({ page: axePage }).analyze();
const badDoc = axeDoc.violations.filter(
  (v) => v.impact === "serious" || v.impact === "critical",
);
check(
  "axe doc: no serious/critical",
  badDoc.length === 0,
  JSON.stringify(badDoc.map((v) => v.id)),
);
await axeContext.close();

// ---- (h) browse search box narrows the table and round-trips (TEA-930) ----
await page.goto(`${BASE}/`, { waitUntil: "load" });
await browseReady();
const beforeSearch = await page.evaluate(() => window.__ewMetrics.rowsRendered);
const histBeforeSearch = await page.evaluate(() => history.length);
await page.fill("#ew-search-input", "Philippines");
await page.waitForFunction(
  () =>
    /^2 documents match/.test(
      document.getElementById("ew-status")?.textContent ?? "",
    ),
  null,
  { timeout: 10000 },
);
const afterSearch = await page.evaluate(() => window.__ewMetrics.rowsRendered);
check(
  "search narrows the row count",
  beforeSearch > afterSearch && afterSearch === 2,
  `${beforeSearch} -> ${afterSearch}`,
);
check(
  "search writes q to the URL",
  new URL(page.url()).searchParams.get("q") === "Philippines",
  page.url(),
);
const histAfterSearch = await page.evaluate(() => history.length);
check(
  "typing uses replaceState (no history growth)",
  histBeforeSearch === histAfterSearch,
  `${histBeforeSearch} -> ${histAfterSearch}`,
);
const searchUrl = page.url();
const restore = await browser.newPage();
await restore.goto(searchUrl, { waitUntil: "load" });
await restore.waitForFunction(
  () => (window.__ewMetrics?.rowsRendered ?? 0) > 0,
  null,
  { timeout: 120000 },
);
check(
  "search box restores from the URL on reload",
  (await restore.inputValue("#ew-search-input")) === "Philippines",
);
check(
  "restored status reflects the filtered set",
  /^2 documents match/.test(await restore.textContent("#ew-status")),
);
await restore.close();

// Export must flush a visible search term even when its debounce has not fired.
await page.goto(`${BASE}/`, { waitUntil: "load" });
await browseReady();
const pendingSearchDownloadPromise = page.waitForEvent("download");
await page.evaluate(() => {
  const input = document.getElementById("ew-search-input");
  input.value = "Philippines";
  input.dispatchEvent(new Event("input", { bubbles: true }));
  document.getElementById("ew-export").click();
});
const pendingSearchDownload = await pendingSearchDownloadPromise;
const pendingSearchPath = await pendingSearchDownload.path();
const pendingSearchCsv =
  pendingSearchPath === null ? "" : await readFile(pendingSearchPath, "utf8");
const pendingSearchRows = parseCsv(pendingSearchCsv).slice(1);
check(
  "export flushes a pending search term",
  pendingSearchRows.length === 2 &&
    pendingSearchRows.every((row) =>
      row.slice(0, 6).some((value) => value.includes("Philippines")),
    ),
  `rows=${pendingSearchRows.length}`,
);
check(
  "pending export writes q to the URL",
  new URL(page.url()).searchParams.get("q") === "Philippines",
);

// ---- (i) a filter change inside the search debounce window keeps the pending term (TEA-930 race regression) ----
await page.goto(`${BASE}/`, { waitUntil: "load" });
await browseReady();
await page.evaluate(() => {
  const input = document.getElementById("ew-search-input");
  input.value = "Philippines";
  input.dispatchEvent(new Event("input", { bubbles: true }));
  // fire a toggle change synchronously, well inside the 250ms debounce window
  const scope = document.getElementById("ew-scope-toggle");
  scope.checked = true;
  scope.dispatchEvent(new Event("change", { bubbles: true }));
});
let racePreserved = false;
try {
  // on the buggy path the term is wiped and never commits, so q never appears
  await page.waitForFunction(
    () => new URLSearchParams(location.search).get("q") === "Philippines",
    null,
    { timeout: 5000 },
  );
  racePreserved =
    (await page.inputValue("#ew-search-input")) === "Philippines" &&
    new URL(page.url()).searchParams.get("scope") === "all";
} catch {
  racePreserved = false;
}
check(
  "filter change mid-debounce keeps the pending search term",
  racePreserved,
  page.url(),
);

// ---- (j) rendered markdown mode (B1 / TEA-929) ----
await page.goto(`${BASE}/doc/synthetic-rich/`, { waitUntil: "load" });
await docReady();
check(
  "rendered mode: container holds a rendered tree",
  (await page.locator("#ew-doc-text .ew-doc-rendered").count()) === 1,
);
check(
  "rendered mode: GFM table rendered",
  (await page.locator("#ew-doc-text table").count()) >= 1,
);
check(
  "rendered mode: toggle shows View raw text",
  (await page.textContent("#ew-view-toggle")) === "View raw text" &&
    (await page.locator("#ew-view-toggle").isVisible()),
);
// The raw markdown is "collective **action** clauses"; the rendered
// concatenation is "collective action clauses", so the spaced query matches
// only after the asterisks are gone (the active-text contract).
await page.fill("#ew-doc-search-input", "collective action clauses");
await page.waitForFunction(
  () =>
    /match/.test(
      document.getElementById("ew-doc-search-count")?.textContent ?? "",
    ),
  null,
  { timeout: 10000 },
);
check(
  "rendered search finds the bold-split phrase",
  /1 match/.test(await page.textContent("#ew-doc-search-count")),
  await page.textContent("#ew-doc-search-count"),
);
await page.click("#ew-doc-search-next");
await page.waitForFunction(
  () =>
    (document.getElementById("ew-doc-live")?.textContent ?? "").includes(
      "Match 1 of 1",
    ),
  null,
  { timeout: 10000 },
);
const richLive = await page.textContent("#ew-doc-live");
check(
  "live region quotes the RENDERED snippet (no ** for a bold-split phrase)",
  richLive.includes("collective action clauses") && !richLive.includes("**"),
  richLive,
);
check(
  "current match painted in rendered mode",
  await page.evaluate(
    () => (CSS.highlights.get("ew-match-current")?.size ?? 0) === 1,
  ),
);
// TOC derived from rendered headings; jump from a heading scrolls and focuses.
await page.locator("#ew-doc-toc-details summary").click();
const richTocRows = await page.locator("#ew-doc-toc button").count();
check(
  "rendered TOC derived from headings",
  richTocRows >= 3,
  `${richTocRows} rows`,
);
// The fixture ends with an intentionally empty heading (a blank `## `); it must
// be skipped, so no contents row is blank and the O(text-nodes) offset fallback
// never fires for it (council PR gate).
check(
  "rendered TOC skips empty headings (no blank rows)",
  await page.evaluate(() =>
    [...document.querySelectorAll("#ew-doc-toc button")].every(
      (b) => (b.textContent ?? "").trim() !== "",
    ),
  ),
  "a blank contents row is present",
);
await page.locator("#ew-doc-toc button").last().click(); // "Events of Default", far down
await page.waitForFunction(() => window.scrollY > 0, null, { timeout: 10000 });
check("rendered heading TOC jump scrolls", true);
check(
  "rendered heading TOC jump focuses text",
  (await page.evaluate(() => document.activeElement?.id)) === "ew-doc-text",
);
// Toggle to raw re-runs the query in raw space (the phrase no longer matches),
// and the container is back to the single-text-node plain path.
await page.click("#ew-view-toggle");
await page.waitForFunction(
  () =>
    document.getElementById("ew-view-toggle")?.textContent ===
    "View formatted text",
  null,
  { timeout: 10000 },
);
await page.waitForFunction(
  () =>
    (
      document.getElementById("ew-doc-search-count")?.textContent ?? ""
    ).includes("No exact matches"),
  null,
  { timeout: 10000 },
);
check(
  "toggle to raw re-runs the query (bold-split phrase no longer matches)",
  true,
  await page.textContent("#ew-doc-search-count"),
);
check(
  "raw mode is the single-text-node plain path",
  await page.evaluate(() => {
    const c = document.getElementById("ew-doc-text");
    return (
      c.firstChild?.nodeType === 3 &&
      c.dataset.segStart === "0" &&
      !c.querySelector(".ew-doc-rendered")
    );
  }),
);
await page.click("#ew-view-toggle");
await page.waitForFunction(
  () =>
    (
      document.getElementById("ew-doc-search-count")?.textContent ?? ""
    ).includes("1 match"),
  null,
  { timeout: 10000 },
);
check(
  "toggle back to formatted re-matches the phrase",
  (await page.locator("#ew-doc-text .ew-doc-rendered").count()) === 1,
);
// ?q= deep link on a rendered doc restores and navigates.
await page.goto(
  `${BASE}/doc/synthetic-rich/?q=${encodeURIComponent("collective action clauses")}`,
  { waitUntil: "load" },
);
await docReady();
await page.waitForFunction(
  () =>
    (document.getElementById("ew-doc-live")?.textContent ?? "").includes(
      "Match 1 of 1",
    ),
  null,
  { timeout: 10000 },
);
check(
  "rendered ?q= deep link restores and navigates",
  /1 match/.test(await page.textContent("#ew-doc-search-count")),
);

// ---- (k) pages-source doc keeps the plain path (regression) ----
await page.goto(`${BASE}/doc/edgar-0001193125-26-273390/`, {
  waitUntil: "load",
});
await docReady();
check(
  "pages-source doc: no view toggle",
  await page.locator("#ew-view-toggle").isHidden(),
);
check(
  "pages-source doc: single text node + seg-start (plain path)",
  await page.evaluate(() => {
    const c = document.getElementById("ew-doc-text");
    return (
      c.firstChild?.nodeType === 3 &&
      c.dataset.segStart === "0" &&
      !c.querySelector(".ew-doc-rendered")
    );
  }),
);
check(
  "pages-source doc: page-boundaries note present",
  (await page.textContent("body")).includes(
    "page boundaries are not displayed",
  ),
);

// ---- (l) self-hosted parquet extension, guarded by SMOKE_EXT_BASE (TEA-932) ----
// The duckdb-wasm worker's extension fetch escapes page-scoped routing, so the
// interception is context-level and installed BEFORE the page is created;
// extensions.duckdb.org is aborted so a mechanism regression fails loudly (rows
// cannot render off the blocked origin) rather than passing via the default CDN.
const extBase = process.env.SMOKE_EXT_BASE;
if (extBase) {
  const extBaseNorm = extBase.replace(/\/+$/, "");
  const extContext = await browser.newContext();
  const extRequests = [];
  await extContext.route("**/*", (route) => {
    const url = route.request().url();
    extRequests.push(url);
    if (url.includes("extensions.duckdb.org")) return route.abort();
    return route.continue();
  });
  const extPage = await extContext.newPage();
  let extRendered = true;
  await extPage.goto(`${BASE}/`, { waitUntil: "load" });
  try {
    await extPage.waitForFunction(
      () => (window.__ewMetrics?.rowsRendered ?? 0) > 0,
      null,
      {
        timeout: 120000,
      },
    );
  } catch {
    extRendered = false;
  }
  const defaultHits = extRequests.filter((u) =>
    u.includes("extensions.duckdb.org"),
  );
  // Assert the full configured base (not just its origin): a dropped path
  // segment (e.g. missing /ext) would still hit the origin but 404 in prod.
  const mirrorHits = extRequests.filter(
    (u) =>
      u.startsWith(extBaseNorm) && u.includes("parquet.duckdb_extension.wasm"),
  );
  check(
    "ext: zero requests to extensions.duckdb.org",
    defaultHits.length === 0,
    `count=${defaultHits.length}`,
  );
  check(
    "ext: parquet extension fetched from mirror base",
    mirrorHits.length >= 1,
    mirrorHits[0] ?? "(none)",
  );
  check("ext: rows render with extensions.duckdb.org blocked", extRendered);
  await extContext.close();
}

// ---- (m) mobile viewport: no horizontal page scroll on the demo screens
// (B7, TEA-935). Wide content (the browse table, rendered-doc tables) scrolls
// inside its own region, so the page's documentElement must never exceed the
// viewport at 390x844. A doc with a ~300-char unbroken filing URL is asserted
// too, so the S5 long-URL wrap fix (.ew-doc-meta td { overflow-wrap: anywhere })
// stays locked on phones: without it that URL blows the page out to many times
// the viewport width. The gate button keeps a 44px-tall tap target. A fresh
// context carries the 390x844 viewport; the desktop page above is left
// untouched. ----
const mobileCtx = await browser.newContext({
  viewport: { width: 390, height: 844 },
});
const mobile = await mobileCtx.newPage();
const noHScroll = () =>
  mobile.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth,
  );
const scrollDims = () =>
  mobile.evaluate(
    () => `${document.documentElement.scrollWidth} <= ${window.innerWidth}`,
  );
// target-size stays enabled so a shrunk control (chip close, gate button, TOC
// entry) fails here at phone width, not just in the desktop axe pass above.
const mobileAxe = async (label) => {
  const res = await new AxeBuilder({ page: mobile })
    .options({ rules: { "target-size": { enabled: true } } })
    .analyze();
  const bad = res.violations.filter(
    (v) => v.impact === "serious" || v.impact === "critical",
  );
  check(
    `axe ${label} (390x844): no serious/critical`,
    bad.length === 0,
    JSON.stringify(bad.map((v) => v.id)),
  );
};

await mobile.goto(`${BASE}/`, { waitUntil: "load" });
await mobile.waitForFunction(
  () => (window.__ewMetrics?.rowsRendered ?? 0) > 0,
  null,
  { timeout: 120000 },
);
check(
  "mobile browse: no horizontal page scroll at 390x844",
  await noHScroll(),
  await scrollDims(),
);
await mobileAxe("browse");

await mobile.goto(`${BASE}/doc/synthetic-rich/`, { waitUntil: "load" });
await mobile.waitForFunction(() => window.__ewDocMetrics !== undefined, null, {
  timeout: 120000,
});
check(
  "mobile rendered doc: no horizontal page scroll at 390x844",
  await noHScroll(),
  await scrollDims(),
);
await mobileAxe("rendered doc");

// luxse-100026526 renders a ~298-char unbroken filing URL in .ew-doc-meta, so
// it is the doc that actually exercises the S5 wrap fix at phone width (the
// synthetic docs have filing_url = null and cannot). This assertion fails if
// .ew-doc-meta td loses overflow-wrap: anywhere, which is what makes it a lock.
await mobile.goto(`${BASE}/doc/luxse-100026526/`, { waitUntil: "load" });
await mobile.waitForFunction(() => window.__ewDocMetrics !== undefined, null, {
  timeout: 120000,
});
check(
  "mobile long-URL doc: no horizontal page scroll at 390x844 (S5 wrap regression)",
  await noHScroll(),
  await scrollDims(),
);
await mobileAxe("long-URL doc");

await mobile.goto(`${BASE}/doc/synthetic-gate/`, { waitUntil: "load" });
await mobile.waitForSelector("#ew-doc-text button", { timeout: 120000 });
check(
  "mobile gate doc: no horizontal page scroll at 390x844",
  await noHScroll(),
  await scrollDims(),
);
// The B7 fix raised the gate button from 34px to 44px tall; assert the height
// specifically (the label is always wider than 44px, so an || width check would
// pass even if the min-height rule regressed). box-sizing: border-box makes the
// bounding-box height the min-height floor, so >= 44 is exact, not sub-pixel.
const gateBox = await mobile.locator("#ew-doc-text button").boundingBox();
check(
  "mobile gate button is a 44px-tall tap target",
  gateBox !== null && gateBox.height >= 44,
  gateBox
    ? `${Math.round(gateBox.width)}x${Math.round(gateBox.height)}`
    : "(no box)",
);
await mobileAxe("gate doc");
await mobileCtx.close();

// ---- Rendered-mode flow lock (Stage 5 audit, TEA-929). The plain path's
// load-bearing white-space: pre-wrap on #ew-doc-text inherits into the
// injected rendered tree unless .ew-doc-rendered resets it, and marked emits
// newline text nodes between block elements (kept in the search haystack by
// design), so an inherited pre-wrap renders every rendered doc with phantom
// blank lines and near-double-height tables. Nothing functional fails when
// that regresses (offsets and text are unchanged), so this computed-style
// check is the only lock. The second check guards the inverse: raw mode must
// keep the facsimile pre-wrap. ----
const flowPage = await browser.newPage();
await flowPage.goto(`${BASE}/doc/synthetic-rich/`, { waitUntil: "load" });
await flowPage.waitForSelector("#ew-doc-text .ew-doc-rendered", {
  timeout: 120000,
});
check(
  "rendered tree uses normal flow (white-space reset)",
  await flowPage.evaluate(() => {
    const el = document.querySelector("#ew-doc-text .ew-doc-rendered");
    return el !== null && getComputedStyle(el).whiteSpace === "normal";
  }),
  "computed white-space on .ew-doc-rendered is not normal",
);
await flowPage.click("#ew-view-toggle");
await flowPage.waitForFunction(
  () => !document.querySelector("#ew-doc-text .ew-doc-rendered"),
  null,
  { timeout: 10000 },
);
check(
  "raw mode keeps the facsimile pre-wrap on #ew-doc-text",
  await flowPage.evaluate(() => {
    const el = document.getElementById("ew-doc-text");
    return el !== null && getComputedStyle(el).whiteSpace === "pre-wrap";
  }),
  "computed white-space on #ew-doc-text is not pre-wrap in raw mode",
);
await flowPage.close();

await browser.close();
const failed = results.filter((r) => !r.ok);
console.log(failed.length ? `SMOKE FAILED: ${failed.length}` : "SMOKE OK");
process.exit(failed.length ? 1 : 0);

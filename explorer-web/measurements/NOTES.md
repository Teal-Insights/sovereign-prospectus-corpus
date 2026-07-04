# Spike measurement notes (TEA-902)

Machine: Mac (Apple Silicon), Node 24.11, Playwright Chromium headless shell 149.
Harness: two origins (pages 127.0.0.1:8080, data 127.0.0.1:8081 with
Access-Control-Allow-Origin: *), brotli-precompressed wasm/js, on-the-fly
gzip for JSON/parquet. Raw records: results.json.

## Run: sample-100 (2026-07-04)

Build (100 docs + index, `astro build`): 1.05 s build phase, 1.67 s wall,
peak RSS 531 MB. dist 73 MB of which 72 MB is _astro (both wasm bundles:
eh 34.24 MB raw / 5.92 MB br, mvp 39.36 MB raw / 6.68 MB br; a browser
downloads exactly one).

| Scenario | Total to first rows | instantiate | register | query1 / query2 |
|---|---|---|---|---|
| cold | 1,489 ms | 414 ms | 906 ms | 24 / 25 ms |
| warm | 718 ms | 387 ms | 185 ms | 24 / 23 ms |
| throttled (4x CPU, 8 Mbps/40 ms) | 7,753 ms | 6,275 ms | 1,176 ms | 28 / 27 ms |

Doc page (45 KB median sample doc): fetch 3 ms, parse 0.1 ms, render 0 ms.

Transfer, cold: 111 KB page-visible (10 requests) + 5.92 MB brotli wasm
fetched inside the worker = ~6.0 MB total. Budgets: cold < 5 s PASS,
warm < 2 s PASS, throttled < 15 s PASS, transfer < 10 MB PASS.

Sovereign default scope, live counts, URL state, back/forward, pagination:
verified by the committed dev smoke (`scripts/smoke.mjs`, run against
`npm run dev` on the real snapshot; 13/13 checks on 2026-07-04).

## Run: full-9774 / full-9774-v2 (2026-07-04)

Two full-scale runs exist in results.json: full-9774 (pre PR-gate code)
and full-9774-v2 (post PR-gate fixes; current code). Numbers below are
v2 with v1 in parentheses where they differ beyond noise; run-to-run
variance is ~10%.

Build (9,775 pages, `astro build` timed directly via /usr/bin/time -l):
4.69 s build phase, 5.34 s wall, peak RSS 683 MB (v1: 4.63 s / 690 MB).
dist 155 MB decimal (148 MiB per du), of which 73.6 MB decimal is the
two wasm bundles; ~6.3 KB HTML per doc page.

| Scenario | Total to first rows | instantiate | parquet fetch | register | query1 / first refresh |
|---|---|---|---|---|---|
| cold | 1,509 ms (1,346) | 426 ms | 63 ms | 678 ms | 26 / 32 ms |
| warm | 850 ms (795) | 391 ms | 62 ms | 185 ms | 24 / 32 ms |
| throttled (4x CPU, 8 Mbps/40 ms) | 9,186 ms (9,101) | 6,272 ms | 1,428 ms | 1,146 ms | 31 / 36 ms |

The "total to first rows" clock starts at the window load event (data
work is deferred past first paint by design), so these numbers EXCLUDE
the initial HTML/CSS/JS download and parse; under throttling that
exclusion is non-trivial. Lighthouse's FCP/LCP (below) cover the
pre-load phase. "first refresh" times the list+count query pair of the
first table render, not a single statement.

Transfer, cold: 2.81 MB page-visible (10 requests; the 1.7 MB parquet
gzips to ~1.4 MB in this harness) + 5.92 MB brotli wasm in the worker
= ~8.7 MB. Note: the harness gzips the parquet on the fly; object
stores gate compression on content-type and typically will NOT compress
application/octet-stream, so production cold transfer is ~0.3 MB higher
(~9.0 MB) unless the host is configured for it.
Budgets: cold < 5 s PASS, warm < 2 s PASS, throttled < 15 s PASS,
transfer < 10 MB PASS (see ARCHITECTURE.md: wasm compression is a hard
host requirement; uncompressed it is 34 MB and blows the budget).

Doc page (729 KB Peru 424B5): fetch 23 ms, parse 0.8 ms, render 0 ms.
Worst case (luxse-100387641, 29 MB Philippines): click-gate engaged;
post-click work is ~0.4 s (fetch 371 ms + JSON parse 48 ms + render
9.5 ms); ~2.8 s wall from navigation to rendered text including page
load and the automated gate click. No tab hang.

Lighthouse (system Chrome headless, served dist): performance 100,
FCP 978 ms, LCP 1,534 ms, TBT 0 ms, CLS 0. (Playwright's
chromium-headless-shell fails with NO_FCP under lighthouse; use system
Chrome or CHROME_PATH.)

bfcache (full-9774-bfcache-v2, measured correctly): browse -> doc ->
back RESTORES from bfcache with the DuckDB worker alive. Verified with
full Chrome launched WITHOUT Playwright's default
--disable-back-forward-cache switch, a page sentinel surviving goBack,
and pageshow.persisted === true; back navigation 159 ms. The earlier
full-9774 bfcache record (backNavMs 846, notRestoredReasons null) is
INVALID as a restore claim: Playwright's default launch disables
bfcache, so that run measured a full reload, and notRestoredReasons
null is not a restore signal. Caught by the council PR gate.

## Hand-verification spot-checks (domain rule)

- edgar-0000903423-02-000767: sec.gov index page shows PERU REPUBLIC OF
  (Filer), 424B5, 2002-11-27; rendered page matches exactly.
- nsm-09954226-3c1c-455e-970d-ac2010ec7e1a: FCA NSM announcement reads
  "THE ARAB REPUBLIC OF EGYPT, Publication of Final Terms, 2 June 2026";
  rendered page matches (PFT, 2026-06-02).
- luxse-100387641: filing_url resolves (HTTP 200, application/pdf,
  15 MB); metadata provenance is the LuxSE GraphQL API.
- pdip-ken67 (null date, null doc_type): renders "undated" and "n/a";
  filing_url (PDIP search page) resolves HTTP 200. Note: PDIP filing_url
  is the generic search page, not a per-document link (S1 data
  limitation, unchanged by this task).

## Measurement caveats

- The wasm fetch happens inside the Web Worker (duckdb-wasm instantiate);
  page-level CDP does not see worker network, so `wasm.transferredBytes`
  reads 0 and `wasmFetchMs` null in the records. Wasm transfer size is
  taken from the served .br files instead; download time is included in
  `instantiateMs` (visible in the throttled run: 414 ms -> 6,275 ms).
- `performance.memory.usedJSHeapSize` is quantized without
  --enable-precise-memory-info (the 10,000,000 reading is a bucket, not a
  precise value). Wasm memory lives in the worker and is not included.
- Localhost network: cold/warm "network" time is effectively zero except
  in the throttled scenario, which is the honest broadband-ish proxy.
- The throttled records' `transferred` summaries undercount (about half
  the requests are missing from CDP capture under
  Network.emulateNetworkConditions); only the un-throttled cold
  `network.transferredBytes` feeds the transfer budget.
- Doc metrics record `stringLength` (UTF-16 code units of the JSON
  body), not bytes; `text_bytes` in the parquet is the exact stored
  size (29,031,849 for the worst case vs stringLength 29,028,574).
- `wasmFetchMs` is null in all records (worker-side fetch invisible to
  page-level CDP and resource timing); closing it needs CDP worker
  auto-attach, filed as a follow-up issue.

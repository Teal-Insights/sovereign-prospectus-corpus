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
verified in the dev smoke (13/13 checks).

## Run: full-9774 (2026-07-04)

Build (9,775 pages, `astro build` timed directly via /usr/bin/time -l):
4.63 s build phase, 5.43 s wall, peak RSS 690 MB. dist 148 MB total
(72 MB wasm assets + ~9,774 doc pages at ~6.3 KB HTML each).

| Scenario | Total to first rows | instantiate | parquet fetch | register | query1 / query2 |
|---|---|---|---|---|---|
| cold | 1,346 ms | 426 ms | 63 ms | 678 ms | 26 / 32 ms |
| warm | 795 ms | 391 ms | 62 ms | 185 ms | 24 / 32 ms |
| throttled (4x CPU, 8 Mbps/40 ms) | 9,101 ms | 6,272 ms | 1,428 ms | 1,146 ms | 31 / 36 ms |

Transfer, cold: 2.81 MB page-visible (10 requests; the 1.7 MB parquet
gzips to ~1.4 MB) + 5.92 MB brotli wasm in the worker = ~8.7 MB.
Budgets: cold < 5 s PASS, warm < 2 s PASS, throttled < 15 s PASS,
transfer < 10 MB PASS (but see ARCHITECTURE.md: wasm compression is a
hard host requirement; uncompressed it is 34 MB and blows the budget).

Doc page (729 KB Peru 424B5): fetch 21 ms, parse 0.8 ms, render 0 ms.
Worst case (luxse-100387641, 29 MB Philippines): click-gate engaged;
after click: fetch 376 ms, JSON parse 40 ms, render 7.8 ms, ~2.8 s wall
from navigation to rendered text. No tab hang.

Lighthouse (system Chrome headless, served dist): performance 100,
FCP 978 ms, LCP 1,534 ms, TBT 0 ms, CLS 0. (Playwright's
chromium-headless-shell fails with NO_FCP under lighthouse; use system
Chrome or CHROME_PATH.)

bfcache: browse -> doc -> back RESTORES from bfcache
(notRestoredReasons null; the DuckDB worker does not block it in
Chromium 149); back navigation ~0.8 s including harness polling.

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

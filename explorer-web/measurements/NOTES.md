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

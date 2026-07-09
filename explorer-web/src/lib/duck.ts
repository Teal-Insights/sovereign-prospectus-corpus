// DuckDB-WASM boot: self-hosted assets via Vite ?url imports (documented
// duckdb.org pattern), selectBundle restricted to mvp + eh (never coi; no
// cross-origin-isolation requirement). DOM-free API: callable from any
// framework island. Browser-only; exercised by the spike, not vitest.

import * as duckdb from '@duckdb/duckdb-wasm';
import wasmEh from '@duckdb/duckdb-wasm/dist/duckdb-eh.wasm?url';
import workerEh from '@duckdb/duckdb-wasm/dist/duckdb-browser-eh.worker.js?url';
import workerMvp from '@duckdb/duckdb-wasm/dist/duckdb-browser-mvp.worker.js?url';
import wasmMvp from '@duckdb/duckdb-wasm/dist/duckdb-mvp.wasm?url';

import { PUBLIC_EXTENSION_BASE_URL, PUBLIC_WASM_BASE_URL } from './config';
import { applyExtensionRepository } from './ext-repo';
import { createDocsViewSql } from './queries';
import { joinUrl } from './urls';

export interface DuckTimings {
  workerMs: number;
  instantiateMs: number;
}

export interface DuckHandle {
  db: duckdb.AsyncDuckDB;
  conn: duckdb.AsyncDuckDBConnection;
  bundleName: 'mvp' | 'eh';
  timings: DuckTimings;
}

// Self-hosted by default; a wrapper may serve the large binaries from its
// data host (PUBLIC_WASM_BASE_URL). Worker JS is ALWAYS same-origin: the
// Worker() constructor is same-origin restricted; the wasm binary is not.
const BUNDLES: duckdb.DuckDBBundles = PUBLIC_WASM_BASE_URL
  ? {
      mvp: { mainModule: joinUrl(PUBLIC_WASM_BASE_URL, 'duckdb-mvp.wasm'), mainWorker: workerMvp },
      eh: { mainModule: joinUrl(PUBLIC_WASM_BASE_URL, 'duckdb-eh.wasm'), mainWorker: workerEh },
    }
  : {
      mvp: { mainModule: wasmMvp, mainWorker: workerMvp },
      eh: { mainModule: wasmEh, mainWorker: workerEh },
    };

// The parquet-extension self-host mechanism (INSTALL ... FROM with a
// custom_extension_repository fallback) lives in ext-repo.ts so its branches
// are unit-tested; see that module's header for the path model and rationale.

let cached: Promise<DuckHandle> | null = null;

async function boot(): Promise<DuckHandle> {
  const t0 = performance.now();
  const bundle = await duckdb.selectBundle(BUNDLES);
  const worker = new Worker(bundle.mainWorker!);
  const db = new duckdb.AsyncDuckDB(new duckdb.VoidLogger(), worker);
  const t1 = performance.now();
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
  const t2 = performance.now();
  const conn = await db.connect();
  await applyExtensionRepository(PUBLIC_EXTENSION_BASE_URL, (sql) => conn.query(sql));
  return {
    db,
    conn,
    bundleName: bundle.mainWorker === workerEh ? 'eh' : 'mvp',
    timings: { workerMs: t1 - t0, instantiateMs: t2 - t1 },
  };
}

export function initDuckDB(): Promise<DuckHandle> {
  if (!cached) {
    cached = boot();
    // Do not memoize a rejection: a transient worker-spawn failure should
    // not brick every later init on the page.
    cached.catch(() => {
      cached = null;
    });
  }
  return cached;
}

const PARQUET_NAME = 'documents.parquet';

export async function registerDocumentsParquet(handle: DuckHandle, bytes: Uint8Array): Promise<void> {
  // Guard against re-registration (dev HMR, script re-run).
  await handle.db.dropFile(PARQUET_NAME).catch(() => undefined);
  await handle.db.registerFileBuffer(PARQUET_NAME, bytes);
  await handle.conn.query(createDocsViewSql(PARQUET_NAME));
}

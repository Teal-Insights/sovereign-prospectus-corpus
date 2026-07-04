// DuckDB-WASM boot: self-hosted assets via Vite ?url imports (documented
// duckdb.org pattern), selectBundle restricted to mvp + eh (never coi; no
// cross-origin-isolation requirement). DOM-free API: callable from any
// framework island. Browser-only; exercised by the spike, not vitest.

import * as duckdb from '@duckdb/duckdb-wasm';
import wasmEh from '@duckdb/duckdb-wasm/dist/duckdb-eh.wasm?url';
import workerEh from '@duckdb/duckdb-wasm/dist/duckdb-browser-eh.worker.js?url';
import workerMvp from '@duckdb/duckdb-wasm/dist/duckdb-browser-mvp.worker.js?url';
import wasmMvp from '@duckdb/duckdb-wasm/dist/duckdb-mvp.wasm?url';

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

const BUNDLES: duckdb.DuckDBBundles = {
  mvp: { mainModule: wasmMvp, mainWorker: workerMvp },
  eh: { mainModule: wasmEh, mainWorker: workerEh },
};

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
  return {
    db,
    conn,
    bundleName: bundle.mainModule === wasmEh ? 'eh' : 'mvp',
    timings: { workerMs: t1 - t0, instantiateMs: t2 - t1 },
  };
}

export function initDuckDB(): Promise<DuckHandle> {
  cached ??= boot();
  return cached;
}

const PARQUET_NAME = 'documents.parquet';

export async function registerDocumentsParquet(handle: DuckHandle, bytes: Uint8Array): Promise<void> {
  // Guard against re-registration (dev HMR, script re-run).
  await handle.db.dropFile(PARQUET_NAME).catch(() => undefined);
  await handle.db.registerFileBuffer(PARQUET_NAME, bytes);
  await handle.conn.query(`CREATE OR REPLACE VIEW docs AS SELECT * FROM read_parquet('${PARQUET_NAME}')`);
}

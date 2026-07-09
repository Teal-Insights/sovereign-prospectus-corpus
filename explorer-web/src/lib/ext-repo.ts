// Redirect the parquet extension fetch away from extensions.duckdb.org (a
// third live origin, an availability SPOF and an institutional-proxy killer)
// to our own data host. DuckDB appends its own
// <core-version>/<wasm-platform>/parquet.duckdb_extension.wasm suffix to the
// repository base, keyed by the DuckDB CORE version inside the wasm build
// (v1.4.3 for duckdb-wasm 1.32.0), NOT the npm version string. So the base
// must be the mirror's parent of that <core-version>/<platform> tree.
//
// When base is unset the app is byte-identical to today: no pragma runs and
// duckdb autoloads from extensions.duckdb.org on the first read_parquet.
// Mechanism order (the local blocked-origin proof, TEA-932 task 3, verifies
// which one actually redirects the fetch): INSTALL ... FROM is preferred
// (deterministic, loads at boot, no reliance on autoload resolution);
// custom_extension_repository is the autoload fallback.
//
// Kept out of duck.ts (which imports duckdb-wasm and astro:env, so it is not
// vitest-testable) and given the base as a parameter, matching config.ts's
// convention, so the three branches are unit-tested (ext-repo.test.ts).
import { sqlQuote } from './queries';

// A minimal runner so this module never imports duckdb-wasm; duck.ts passes
// `(sql) => conn.query(sql)`.
export type ExtRepoQuery = (sql: string) => Promise<unknown>;

export async function applyExtensionRepository(
  base: string | undefined,
  runQuery: ExtRepoQuery
): Promise<void> {
  if (!base) return;
  const quoted = sqlQuote(base);
  try {
    await runQuery(`INSTALL parquet FROM ${quoted}`);
    await runQuery('LOAD parquet');
  } catch (err) {
    // The DB uses VoidLogger, so surface the primary-path failure here: without
    // this the fallback is silent and a broken mirror only resurfaces later as
    // an unattributed read_parquet error.
    console.warn(
      '[ext] INSTALL/LOAD parquet from the mirror failed; falling back to custom_extension_repository',
      err
    );
    await runQuery(`SET custom_extension_repository=${quoted}`);
  }
}

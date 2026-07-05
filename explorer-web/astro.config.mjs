import path from 'node:path';
import { defineConfig, envField } from 'astro/config';
import { loadEnv } from 'vite';
import { snapshotDevMiddleware } from './integrations/snapshot-dev-middleware.mjs';

// .env files are not auto-loaded inside config files; merge them under the
// shell environment so an exported var always wins.
const env = { ...loadEnv('', process.cwd(), ''), ...process.env };
const SNAPSHOT_DIR = path.resolve(process.cwd(), env.SNAPSHOT_DIR ?? '../data/snapshot');

// Build detection keys off argv, which covers the CLI paths this project
// uses (astro build via npm script or npx). Programmatic builds through the
// Astro JS API would bypass this gate; the astro:env schema below still
// enforces presence there.
const isBuild = process.argv.includes('build');
const dataUrl = env.PUBLIC_DATA_BASE_URL;
if (isBuild) {
  if (!dataUrl) {
    throw new Error(
      'PUBLIC_DATA_BASE_URL must be set explicitly for production builds (e.g. https://data.example.org/snapshot)'
    );
  }
  let u;
  try {
    u = new URL(dataUrl);
  } catch {
    throw new Error(
      `PUBLIC_DATA_BASE_URL must be an absolute URL (e.g. https://data.example.org/snapshot); got ${dataUrl}`
    );
  }
  const LOCAL_HOSTS = ['localhost', '127.0.0.1', '[::1]'];
  const isLocal = LOCAL_HOSTS.includes(u.hostname);
  if (u.protocol !== 'https:' && !isLocal) {
    throw new Error(`PUBLIC_DATA_BASE_URL must be https (mixed content); got ${dataUrl}`);
  }
  const wasmUrl = env.PUBLIC_WASM_BASE_URL;
  if (wasmUrl) {
    let w;
    try {
      w = new URL(wasmUrl);
    } catch {
      throw new Error(`PUBLIC_WASM_BASE_URL must be an absolute URL when set; got ${wasmUrl}`);
    }
    const wLocal = LOCAL_HOSTS.includes(w.hostname);
    if (w.protocol !== 'https:' && !wLocal) {
      throw new Error(`PUBLIC_WASM_BASE_URL must be https (mixed content); got ${wasmUrl}`);
    }
  }
}

export default defineConfig({
  output: 'static',
  trailingSlash: 'always',
  env: {
    schema: {
      PUBLIC_DATA_BASE_URL: envField.string({ context: 'client', access: 'public' }),
      PUBLIC_WASM_BASE_URL: envField.string({ context: 'client', access: 'public', optional: true }),
    },
  },
  integrations: [snapshotDevMiddleware(SNAPSHOT_DIR)],
  vite: { optimizeDeps: { exclude: ['@duckdb/duckdb-wasm'] } },
});

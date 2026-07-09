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
  const extUrl = env.PUBLIC_EXTENSION_BASE_URL;
  if (extUrl) {
    let e;
    try {
      e = new URL(extUrl);
    } catch {
      throw new Error(`PUBLIC_EXTENSION_BASE_URL must be an absolute URL when set; got ${extUrl}`);
    }
    const eLocal = LOCAL_HOSTS.includes(e.hostname);
    if (e.protocol !== 'https:' && !eLocal) {
      throw new Error(`PUBLIC_EXTENSION_BASE_URL must be https (mixed content); got ${extUrl}`);
    }
    // duckdb appends /<core>/<platform>/<name>; a trailing slash on the base
    // yields a double-slash key that 404s (no CDN fallback catches it).
    if (extUrl.endsWith('/')) {
      throw new Error(
        `PUBLIC_EXTENSION_BASE_URL must not end with a slash (duckdb appends /<core>/<platform>/<name>); got ${extUrl}`
      );
    }
  }
  // Version lockstep: the extension mirror lives under the same duckdb-wasm-<v>
  // prefix as the wasm binaries, so a pin bump that moves one URL but not the
  // other would silently serve a mismatched extension. If both are set, require
  // their duckdb-wasm-<v> segments to match (fails the build loudly, mirroring
  // build.sh's PUBLIC_WASM_BASE_URL drift guard in the wrapper).
  if (extUrl && wasmUrl) {
    const seg = (u) => u.match(/duckdb-wasm-[^/]+/)?.[0];
    const wv = seg(wasmUrl);
    const xv = seg(extUrl);
    if (wv && xv && wv !== xv) {
      throw new Error(
        `PUBLIC_EXTENSION_BASE_URL (${xv}) must share the duckdb-wasm version of PUBLIC_WASM_BASE_URL (${wv}); bump them together`
      );
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
      PUBLIC_EXTENSION_BASE_URL: envField.string({ context: 'client', access: 'public', optional: true }),
    },
  },
  integrations: [snapshotDevMiddleware(SNAPSHOT_DIR)],
  vite: { optimizeDeps: { exclude: ['@duckdb/duckdb-wasm'] } },
});

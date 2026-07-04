import path from 'node:path';
import { defineConfig, envField } from 'astro/config';
import { loadEnv } from 'vite';
import { snapshotDevMiddleware } from './integrations/snapshot-dev-middleware.mjs';

// .env files are not auto-loaded inside config files; merge them under the
// shell environment so an exported var always wins.
const env = { ...loadEnv('', process.cwd(), ''), ...process.env };
const SNAPSHOT_DIR = path.resolve(process.cwd(), env.SNAPSHOT_DIR ?? '../data/snapshot');

const isBuild = process.argv.includes('build');
const dataUrl = env.PUBLIC_DATA_BASE_URL;
if (isBuild) {
  if (!dataUrl) {
    throw new Error(
      'PUBLIC_DATA_BASE_URL must be set explicitly for production builds (e.g. https://data.example.org/snapshot)'
    );
  }
  const u = new URL(dataUrl);
  const isLocal = u.hostname === 'localhost' || u.hostname === '127.0.0.1';
  if (u.protocol !== 'https:' && !isLocal) {
    throw new Error(`PUBLIC_DATA_BASE_URL must be https (mixed content); got ${dataUrl}`);
  }
}

export default defineConfig({
  output: 'static',
  trailingSlash: 'always',
  env: {
    schema: {
      PUBLIC_DATA_BASE_URL: envField.string({ context: 'client', access: 'public' }),
    },
  },
  integrations: [snapshotDevMiddleware(SNAPSHOT_DIR)],
  vite: { optimizeDeps: { exclude: ['@duckdb/duckdb-wasm'] } },
});

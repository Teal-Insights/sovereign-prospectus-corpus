// Static server for the spike measurement harness (and manual served-build
// use). Serves --dir on --port; --cors adds Access-Control-Allow-Origin: *
// (the data origin in the two-origin harness). Compression mirrors what a
// production host must do: precompressed .br/.gz served with the correct
// Content-Encoding when present (wasm), on-the-fly gzip for compressible
// text types (json/parquet/html/js/css). Real 404s, no SPA fallback.
//
//   node scripts/serve-static.mjs --dir dist --port 8080
//   node scripts/serve-static.mjs --dir ../data/snapshot --port 8081 --cors
//   node scripts/serve-static.mjs --precompress dist   # one-shot .br for wasm/js

import { createReadStream, existsSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { brotliCompressSync, constants, gzipSync } from 'node:zlib';

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript',
  '.mjs': 'text/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.parquet': 'application/octet-stream',
  '.wasm': 'application/wasm',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
};
const GZIP_TYPES = new Set(['.html', '.js', '.mjs', '.css', '.json', '.parquet', '.svg']);

function arg(name) {
  const i = process.argv.indexOf(`--${name}`);
  return i === -1 ? undefined : process.argv[i + 1];
}
const hasFlag = (name) => process.argv.includes(`--${name}`);

if (arg('precompress')) {
  const { readdirSync } = await import('node:fs');
  const root = path.resolve(arg('precompress'));
  const files = [];
  const visit = (dir) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, entry.name);
      if (entry.isDirectory()) visit(p);
      else if (/\.(wasm|js)$/.test(entry.name)) files.push(p);
    }
  };
  visit(root);
  for (const file of files) {
    const target = `${file}.br`;
    if (existsSync(target)) continue;
    const raw = readFileSync(file);
    const compressed = brotliCompressSync(raw, {
      params: { [constants.BROTLI_PARAM_QUALITY]: 9 },
    });
    writeFileSync(target, compressed);
    console.log(`precompressed ${path.relative(root, file)}: ${raw.length} -> ${compressed.length}`);
  }
  process.exit(0);
}

const dir = path.resolve(arg('dir') ?? '.');
const port = Number(arg('port') ?? 8080);
const cors = hasFlag('cors');

const server = http.createServer((req, res) => {
  const urlPath = decodeURIComponent(new URL(req.url ?? '/', 'http://x').pathname);
  let filePath = path.resolve(dir, '.' + urlPath);
  if (!filePath.startsWith(dir + path.sep) && filePath !== dir) {
    res.statusCode = 403;
    res.end('forbidden');
    return;
  }
  if (existsSync(filePath) && statSync(filePath).isDirectory()) {
    filePath = path.join(filePath, 'index.html');
  }
  if (!existsSync(filePath) || !statSync(filePath).isFile()) {
    res.statusCode = 404;
    if (cors) res.setHeader('Access-Control-Allow-Origin', '*');
    res.end('not found');
    return;
  }

  const ext = path.extname(filePath);
  res.setHeader('Content-Type', MIME[ext] ?? 'application/octet-stream');
  if (cors) res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Vary', 'Accept-Encoding');

  const accepts = String(req.headers['accept-encoding'] ?? '');
  if (accepts.includes('br') && existsSync(`${filePath}.br`)) {
    res.setHeader('Content-Encoding', 'br');
    createReadStream(`${filePath}.br`).pipe(res);
    return;
  }
  if (accepts.includes('gzip') && existsSync(`${filePath}.gz`)) {
    res.setHeader('Content-Encoding', 'gzip');
    createReadStream(`${filePath}.gz`).pipe(res);
    return;
  }
  if (accepts.includes('gzip') && GZIP_TYPES.has(ext)) {
    res.setHeader('Content-Encoding', 'gzip');
    res.end(gzipSync(readFileSync(filePath)));
    return;
  }
  createReadStream(filePath).pipe(res);
});

server.listen(port, '127.0.0.1', () => {
  console.log(`serve-static: ${dir} on http://127.0.0.1:${port} cors=${cors}`);
});

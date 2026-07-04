import fs from 'node:fs';
import path from 'node:path';

const TYPES = {
  '.json': 'application/json',
  '.parquet': 'application/octet-stream',
};

// Serves SNAPSHOT_DIR at /data during `astro dev` only. Real 404s (no SPA
// fallback) so local runs surface missing objects the way a production
// object store would. Absent in `astro preview` by design.
export function snapshotDevMiddleware(snapshotDir) {
  return {
    name: 'snapshot-dev-middleware',
    hooks: {
      'astro:server:setup': ({ server }) => {
        server.middlewares.use('/data', (req, res) => {
          let urlPath;
          try {
            urlPath = decodeURIComponent(new URL(req.url ?? '/', 'http://x').pathname);
          } catch {
            res.statusCode = 400;
            res.end('bad request');
            return;
          }
          const filePath = path.resolve(snapshotDir, '.' + urlPath);
          if (
            !filePath.startsWith(snapshotDir + path.sep) ||
            !fs.existsSync(filePath) ||
            !fs.statSync(filePath).isFile()
          ) {
            res.statusCode = 404;
            res.end('not found');
            return;
          }
          res.setHeader('Content-Type', TYPES[path.extname(filePath)] ?? 'application/octet-stream');
          fs.createReadStream(filePath).pipe(res);
        });
      },
    },
  };
}

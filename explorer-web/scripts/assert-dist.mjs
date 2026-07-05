// CI gate: every snapshot slug must have a pre-rendered page in dist/.
// Run from explorer-web/ after a build, with the SAME SNAPSHOT_DIR the
// build used (defaults to the fixture, matching CI). NOTE: reads
// process.env only; astro.config additionally merges .env via loadEnv,
// so a build driven by a .env SNAPSHOT_DIR needs the var exported for
// this script too.
import { existsSync } from 'node:fs';
import path from 'node:path';

import { asyncBufferFromFile, parquetReadObjects } from 'hyparquet';

const snapshotDir = process.env.SNAPSHOT_DIR ?? 'tests/fixtures/snapshot';
const fixtureParquet = path.join(snapshotDir, 'documents.parquet');
const file = await asyncBufferFromFile(fixtureParquet);
const rows = await parquetReadObjects({ file, columns: ['slug'] });

const expected = [
  'dist/index.html',
  'dist/404.html',
  ...rows.map((r) => `dist/doc/${r.slug}/index.html`),
];
const missing = expected.filter((p) => !existsSync(path.resolve(p)));

if (missing.length) {
  console.error(`assert-dist: ${missing.length} expected route file(s) missing:`);
  for (const m of missing) console.error(`  ${m}`);
  process.exit(1);
}
console.log(`assert-dist: all ${expected.length} expected routes present`);

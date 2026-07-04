// CI gate: every fixture slug must have a pre-rendered page in dist/.
// Run from explorer-web/ after a fixture build.
import { existsSync } from 'node:fs';
import path from 'node:path';

import { asyncBufferFromFile, parquetReadObjects } from 'hyparquet';

const fixtureParquet = 'tests/fixtures/snapshot/documents.parquet';
const file = await asyncBufferFromFile(fixtureParquet);
const rows = await parquetReadObjects({ file, columns: ['slug'] });

const expected = ['dist/index.html', ...rows.map((r) => `dist/doc/${r.slug}/index.html`)];
const missing = expected.filter((p) => !existsSync(path.resolve(p)));

if (missing.length) {
  console.error(`assert-dist: ${missing.length} expected route file(s) missing:`);
  for (const m of missing) console.error(`  ${m}`);
  process.exit(1);
}
console.log(`assert-dist: all ${expected.length} expected routes present`);

import { expect, it } from 'vitest';

import { docPath, joinUrl, manifestUrl, parquetUrl, textUrl } from '../../src/lib/urls';

it('joins with exactly one slash', () => {
  expect(joinUrl('https://d.example/snap', 'MANIFEST.json')).toBe('https://d.example/snap/MANIFEST.json');
  expect(joinUrl('https://d.example/snap/', '/MANIFEST.json')).toBe('https://d.example/snap/MANIFEST.json');
  expect(joinUrl('/data', 'text/x.json')).toBe('/data/text/x.json');
});

it('manifest url has no version token', () => {
  expect(manifestUrl('/data')).toBe('/data/MANIFEST.json');
});

it('doc route path', () => {
  expect(docPath('nsm-101126915')).toBe('/doc/nsm-101126915/');
});

it('version tokens are encoded (real generated_at contains + and :)', () => {
  expect(textUrl('/data', 'nsm-1', '2026-07-04T17:04:09+00:00')).toBe(
    '/data/text/nsm-1.json?v=2026-07-04T17%3A04%3A09%2B00%3A00'
  );
  expect(parquetUrl('/data', '2026-07-04T17:04:09+00:00')).toBe(
    '/data/documents.parquet?v=2026-07-04T17%3A04%3A09%2B00%3A00'
  );
});

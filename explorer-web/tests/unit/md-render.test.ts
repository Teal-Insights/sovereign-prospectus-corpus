import { expect, it } from 'vitest';

import { renderDocMarkdown } from '../../src/lib/md-render';

it('headings map to h1 through h6', () => {
  const h = renderDocMarkdown('# A\n\n## B\n\n### C\n\n#### D\n\n##### E\n\n###### F');
  for (const n of [1, 2, 3, 4, 5, 6]) expect(h).toContain(`<h${n}>`);
});

it('GFM table emits a table element', () => {
  const h = renderDocMarkdown('| A | B |\n| --- | --- |\n| 1 | 2 |');
  expect(h).toContain('<table>');
  expect(h).toContain('<td>1</td>');
});

it('bold emits strong', () => {
  expect(renderDocMarkdown('collective **action** clauses')).toContain('<strong>action</strong>');
});

it('raw HTML is dropped, never passed through (script tag)', () => {
  const h = renderDocMarkdown('before <script>alert(1)</script> after');
  expect(h).not.toContain('<script');
});

it('Docling image comments are dropped, never passed through', () => {
  const h = renderDocMarkdown('text\n\n<!-- image -->\n\nmore');
  expect(h).not.toContain('<!--');
});

it('inline raw HTML is dropped too', () => {
  expect(renderDocMarkdown('a <b>bold</b> c')).not.toContain('<b>');
});

it('a javascript: link renders as text, not an anchor', () => {
  const h = renderDocMarkdown('[click](javascript:alert(1))');
  expect(h).not.toContain('<a ');
  expect(h).toContain('click');
});

it('an https link renders as an anchor with rel noopener', () => {
  const h = renderDocMarkdown('[example](https://example.org)');
  expect(h).toContain('href="https://example.org"');
  expect(h).toContain('rel="noopener"');
  expect(h).toContain('>example</a>');
});

it('an http link also becomes an anchor with rel noopener', () => {
  expect(renderDocMarkdown('[x](http://example.org/a)')).toMatch(
    /<a href="http:\/\/example\.org\/a" rel="noopener">x<\/a>/
  );
});

it('relative and other-scheme links render as plain text', () => {
  expect(renderDocMarkdown('[rel](/local/path)')).not.toContain('<a ');
  expect(renderDocMarkdown('[mail](mailto:x@y.z)')).not.toContain('<a ');
});

it('image syntax renders its alt text only', () => {
  const h = renderDocMarkdown('![alt text](https://x/y.png)');
  expect(h).not.toContain('<img');
  expect(h).toContain('alt text');
});

it('image with no alt renders nothing and leaks no url', () => {
  const h = renderDocMarkdown('![](https://x/y.png)');
  expect(h).not.toContain('<img');
  expect(h).not.toContain('y.png');
});

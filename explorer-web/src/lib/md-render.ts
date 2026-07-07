// Pure, DOM-free markdown-to-HTML rendering for the document page rendered
// mode. String-to-string so it is node-testable; the browser injection site
// (doc-text.ts) pipes the output through DOMPurify as defense in depth, so a
// renderer regression can never become live XSS on untrusted filing text.
//
// Raw HTML tokens (block and inline, including Docling's `<!-- image -->`
// comments) are dropped via a renderer override, never passed through and
// never regex-stripped. GFM tables are on. Link and image handling is added
// in a later task (test-driven); this minimal renderer proves the offset
// mapping risk in the walking skeleton.

import { Marked } from 'marked';

const md = new Marked({
  gfm: true,
  async: false,
  renderer: {
    // Drop raw HTML (both block-level Tokens.HTML and inline Tokens.Tag),
    // including `<!-- image -->` comment noise, without regex-stripping.
    html: () => '',
  },
});

export function renderDocMarkdown(raw: string): string {
  return md.parse(raw) as string;
}

// Pure, DOM-free markdown-to-HTML rendering for the document page rendered
// mode. String-to-string so it is node-testable; the browser injection site
// (doc-text.ts) additionally pipes the output through DOMPurify as defense in
// depth, so a renderer regression can never become live XSS on untrusted
// filing text.
//
// Rules (TEA-929):
//   - Raw HTML tokens (block Tokens.HTML and inline Tokens.Tag, including
//     Docling's `<!-- image -->` comments) are dropped via a renderer
//     override, never passed through and never regex-stripped.
//   - GFM tables are on.
//   - Images render as their alt text, or nothing.
//   - Links become anchors only for http/https hrefs (with rel="noopener");
//     any other scheme (javascript:, mailto:, relative) renders as plain
//     text.

import { Marked, type Tokens } from 'marked';

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function isHttpUrl(href: string): boolean {
  return /^https?:\/\//i.test(href.trim());
}

const md = new Marked({
  gfm: true,
  async: false,
  renderer: {
    // Drop raw HTML (block-level Tokens.HTML and inline Tokens.Tag),
    // including `<!-- image -->` comment noise, without regex-stripping.
    html: () => '',
    // Images: alt text only, never an <img> (no off-origin image loads from
    // untrusted filing text).
    image({ text }: Tokens.Image): string {
      return text ? escapeHtml(text) : '';
    },
    // Links: anchors only for http/https; everything else renders as the
    // link's inner text. `this.parser` is the active parser during render.
    link(this: { parser: { parseInline(tokens: Tokens.Generic[]): string } }, token: Tokens.Link): string {
      const inner = this.parser.parseInline(token.tokens);
      if (isHttpUrl(token.href)) {
        return `<a href="${escapeHtml(token.href)}" rel="noopener">${inner}</a>`;
      }
      return inner;
    },
  },
});

export function renderDocMarkdown(raw: string): string {
  return md.parse(raw) as string;
}

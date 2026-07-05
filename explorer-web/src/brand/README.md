# Brand slots

A private re-theming wrapper may place two optional Astro components
here at build time (this directory ships empty; *.astro is gitignored):

- `Head.astro`: rendered at the end of the authored `<head>` on every
  page (before Astro's hoisted stylesheet link, which is what font
  preloads want). Use for favicon links, font preloads, analytics,
  build stamps.
- `Header.astro`: replaces the neutral `<header class="ew-header">`.
  Keep the `ew-header` class (or an equivalent) and re-measure
  `--ew-jump-offset` against the new header height.

Rules: markup and assets only, no application logic; style values come
from tokens (`--ew-*`); nothing licensed or brand-specific may be
committed to THIS repository.

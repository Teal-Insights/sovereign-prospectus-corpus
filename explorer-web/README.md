# explorer-web

Static web explorer for the sovereign prospectus corpus snapshot
(Astro + DuckDB-WASM). Scaffolded in S2 (Linear TEA-902); decisions and
spike measurements live in [ARCHITECTURE.md](./ARCHITECTURE.md).

## Quick start

```bash
npm install
npm run dev          # serves the app; the repo snapshot at ../data/snapshot
                     # is exposed at /data by a dev-only middleware
npm test             # vitest unit tests
npm run check        # astro check (types)
```

## Building

Production builds require both config values explicitly:

```bash
SNAPSHOT_DIR=../data/snapshot \
PUBLIC_DATA_BASE_URL=https://data.example.org/snapshot \
npm run build
```

- `SNAPSHOT_DIR`: build-time path to the snapshot (pre-renders one page per
  document). Read in `astro.config.mjs`; `.env` files are not auto-loaded
  there, so export it in the shell.
- `PUBLIC_DATA_BASE_URL`: client-side base URL for `MANIFEST.json`,
  `documents.parquet`, and `text/<slug>.json`. The build fails fast if it
  is missing or non-https (localhost excepted).

`astro preview` does NOT serve `/data`; for a served build use
`scripts/serve-static.mjs` (see ARCHITECTURE.md, Measurements).

## CI

The `explorer-web` job builds against the committed fixture at
`tests/fixtures/snapshot` (regenerate with
`uv run python explorer-web/scripts/make_fixture.py` from the repo root).

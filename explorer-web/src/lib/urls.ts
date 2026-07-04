// Pure URL assembly for the snapshot contract. Version tokens implement the
// MANIFEST-first caching model: parquet and text are overwritten in place at
// stable URLs, so both carry ?v=<generated_at> (the manifest itself never
// does; it is fetched no-store).

export function joinUrl(base: string, path: string): string {
  return `${base.replace(/\/+$/, '')}/${path.replace(/^\/+/, '')}`;
}

export function manifestUrl(base: string): string {
  return joinUrl(base, 'MANIFEST.json');
}

export function parquetUrl(base: string, generatedAt: string): string {
  return `${joinUrl(base, 'documents.parquet')}?v=${encodeURIComponent(generatedAt)}`;
}

export function textUrl(base: string, slug: string, generatedAt: string): string {
  return `${joinUrl(base, `text/${slug}.json`)}?v=${encodeURIComponent(generatedAt)}`;
}

// App-internal route (root-relative; the site assumes origin-root deployment,
// recorded as a hosting constraint in ARCHITECTURE.md).
export function docPath(slug: string): string {
  return `/doc/${slug}/`;
}

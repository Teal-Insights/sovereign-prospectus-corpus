// Build-time snapshot access: reads documents.parquet with hyparquet (pure
// JS; snappy is built in) for getStaticPaths, and MANIFEST.json for build
// stamping. Runs in Node only; never shipped to the browser.

import { readFile } from 'node:fs/promises';
import path from 'node:path';

import { asyncBufferFromFile, parquetReadObjects } from 'hyparquet';

export interface DocRow {
  slug: string;
  document_id: number | null;
  storage_key: string | null;
  source: string | null;
  native_id: string | null;
  display_name: string | null;
  issuer_name: string | null;
  title: string | null;
  doc_type: string | null;
  publication_date: string | null;
  country_code: string | null;
  country_name: string | null;
  region: string | null;
  income_group: string | null;
  lending_category: string | null;
  is_sovereign: boolean | null;
  filing_url: string | null;
  page_count: number | null;
  has_text: boolean | null;
  text_source: string | null;
  text_chars: number | null;
  text_bytes: number | null;
  no_text_reason: string | null;
}

export interface SnapshotStamp {
  snapshot_date: string;
  generated_at: string;
}

// SNAPSHOT_DIR is read lazily (not at module scope): ESM imports hoist, so a
// module-scope read would capture the default before test files can set the
// env var.
function snapshotDir(): string {
  return path.resolve(process.cwd(), process.env.SNAPSHOT_DIR ?? '../data/snapshot');
}

function toNull<T>(v: T | undefined | null): T | null {
  return v === undefined || v === null ? null : v;
}

function toNumber(v: unknown): number | null {
  if (v === undefined || v === null) return null;
  return Number(v);
}

function toIsoDate(v: unknown): string | null {
  if (v === undefined || v === null) return null;
  if (v instanceof Date) return v.toISOString().slice(0, 10);
  return String(v).slice(0, 10);
}

let cache: Promise<DocRow[]> | null = null;

async function readParquet(): Promise<DocRow[]> {
  const file = await asyncBufferFromFile(path.join(snapshotDir(), 'documents.parquet'));
  const raw = (await parquetReadObjects({ file })) as Record<string, unknown>[];
  return raw.map((r) => ({
    slug: String(r.slug),
    document_id: toNumber(r.document_id),
    storage_key: toNull(r.storage_key as string),
    source: toNull(r.source as string),
    native_id: toNull(r.native_id as string),
    display_name: toNull(r.display_name as string),
    issuer_name: toNull(r.issuer_name as string),
    title: toNull(r.title as string),
    doc_type: toNull(r.doc_type as string),
    publication_date: toIsoDate(r.publication_date),
    country_code: toNull(r.country_code as string),
    country_name: toNull(r.country_name as string),
    region: toNull(r.region as string),
    income_group: toNull(r.income_group as string),
    lending_category: toNull(r.lending_category as string),
    is_sovereign: toNull(r.is_sovereign as boolean),
    filing_url: toNull(r.filing_url as string),
    page_count: toNumber(r.page_count),
    has_text: toNull(r.has_text as boolean),
    text_source: toNull(r.text_source as string),
    text_chars: toNumber(r.text_chars),
    text_bytes: toNumber(r.text_bytes),
    no_text_reason: toNull(r.no_text_reason as string),
  }));
}

export function loadDocuments(): Promise<DocRow[]> {
  cache ??= readParquet();
  return cache;
}

export async function loadSnapshotManifest(): Promise<SnapshotStamp> {
  const raw = await readFile(path.join(snapshotDir(), 'MANIFEST.json'), 'utf8');
  const m = JSON.parse(raw) as SnapshotStamp;
  return { snapshot_date: m.snapshot_date, generated_at: m.generated_at };
}

// ---- S3 additions (TEA-903): pure aggregations for the baked static shell.
// Callers pass `await loadDocuments()`; no I/O here.

export interface CorpusStats {
  docs: number;
  sources: number;
  issuers: number;
  sovereign: number;
  related: number;
}

export function computeStats(rows: DocRow[]): CorpusStats {
  const sources = new Set<string>();
  const issuers = new Set<string>();
  let sovereign = 0;
  for (const r of rows) {
    if (r.source !== null) sources.add(r.source);
    if (r.issuer_name !== null) issuers.add(r.issuer_name);
    if (r.is_sovereign === true) sovereign += 1;
  }
  return {
    docs: rows.length,
    sources: sources.size,
    issuers: issuers.size,
    sovereign,
    related: rows.length - sovereign,
  };
}

export interface CountryOption {
  code: string;
  name: string;
}

export interface FilterOptions {
  countries: CountryOption[];
  regions: string[];
  incomes: string[];
  sources: string[];
}

export function computeFilterOptions(rows: DocRow[]): FilterOptions {
  const countries = new Map<string, string>();
  const regions = new Set<string>();
  const incomes = new Set<string>();
  const sources = new Set<string>();
  for (const r of rows) {
    // null codes dropped on purpose (synthetic fixture rows stay out of
    // the baked options; null-country docs are unreachable via the filter,
    // matching v1).
    if (r.country_code !== null && r.country_name !== null) {
      countries.set(r.country_code, r.country_name);
    }
    regions.add(r.region ?? 'Unknown');
    incomes.add(r.income_group ?? 'Unknown');
    if (r.source !== null) sources.add(r.source);
  }
  return {
    countries: [...countries.entries()]
      .map(([code, name]) => ({ code, name }))
      .sort((a, b) => a.name.localeCompare(b.name)),
    regions: [...regions].sort(),
    incomes: [...incomes].sort(),
    sources: [...sources].sort(),
  };
}

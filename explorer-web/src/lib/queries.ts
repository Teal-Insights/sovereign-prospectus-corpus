// All SQL for the browse page lives here (framework-agnostic; S3 reuses it).
// The client scripts never assemble SQL. Only `import type` from duckdb-wasm
// so no value import enters the vitest graph; this module must never import
// duck.ts (the connection arrives as a parameter).

import type { AsyncDuckDBConnection } from '@duckdb/duckdb-wasm';

export interface BrowseFilters {
  country?: string;
  source?: string;
  includeNonSovereign: boolean;
  page: number;
  pageSize: number;
}

export interface BrowseRow {
  slug: string;
  display_name: string | null;
  issuer_name: string | null;
  publication_date: string | null;
  country_name: string | null;
  doc_type: string | null;
  source: string | null;
  is_sovereign: boolean | null;
}

export function sqlQuote(v: string): string {
  return `'${v.replaceAll("'", "''")}'`;
}

// The docs view is the single named contract between registration (duck.ts)
// and the query builders below; the bootstrap SQL lives here so every SQL
// string in the app is in this file.
export function createDocsViewSql(parquetName: string): string {
  return `CREATE OR REPLACE VIEW docs AS SELECT * FROM read_parquet(${sqlQuote(parquetName)})`;
}

function whereClause(f: Pick<BrowseFilters, 'country' | 'source' | 'includeNonSovereign'>): string {
  const conditions: string[] = [];
  if (!f.includeNonSovereign) conditions.push('is_sovereign = true');
  if (f.country) conditions.push(`country_name = ${sqlQuote(f.country)}`);
  if (f.source) conditions.push(`source = ${sqlQuote(f.source)}`);
  return conditions.length ? `WHERE ${conditions.join(' AND ')}` : '';
}

export function buildListSql(f: BrowseFilters): string {
  // strftime keeps dates as ISO strings end to end; Arrow JS's Date32
  // representation has varied across versions (Date objects vs epoch-ms).
  return `
    SELECT slug, display_name, issuer_name,
           strftime(publication_date, '%Y-%m-%d') AS publication_date,
           country_name, doc_type, source, is_sovereign
    FROM docs
    ${whereClause(f)}
    ORDER BY publication_date DESC NULLS LAST, slug DESC
    LIMIT ${f.pageSize} OFFSET ${f.page * f.pageSize}
  `;
}

export function buildCountSql(f: BrowseFilters): string {
  return `SELECT count(*)::INTEGER AS n FROM docs ${whereClause(f)}`;
}

export function buildScopeCountsSql(): string {
  return `
    SELECT
      count(*)::INTEGER AS total,
      count(*) FILTER (is_sovereign = true)::INTEGER AS sovereign
    FROM docs
  `;
}

export function buildDistinctSql(col: 'country_name' | 'source'): string {
  return `SELECT DISTINCT ${col} AS v FROM docs WHERE ${col} IS NOT NULL ORDER BY v`;
}

export async function runQuery(
  conn: AsyncDuckDBConnection,
  sql: string
): Promise<Record<string, unknown>[]> {
  const result = await conn.query(sql);
  return result.toArray().map((row) => row.toJSON() as Record<string, unknown>);
}

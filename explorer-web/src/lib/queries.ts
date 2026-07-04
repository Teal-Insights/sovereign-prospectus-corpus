// All SQL for the browse page lives here (framework-agnostic; S3 reuses it).
// The client scripts never assemble SQL. Only `import type` from duckdb-wasm
// so no value import enters the vitest graph; this module must never import
// duck.ts (the connection arrives as a parameter).

import type { AsyncDuckDBConnection } from '@duckdb/duckdb-wasm';

export interface BrowseFilters {
  // S3 multi-select filters (absent = empty). page stays 0-based internal.
  countries?: string[];
  regions?: string[];
  incomes?: string[];
  sources?: string[];
  includeNonSovereign: boolean;
  includeHighIncome?: boolean;
  page: number;
  pageSize: number;
  // Legacy S2 single-value fields, consumed only by the legacy builders
  // below; both go away with the scripts/browse.ts rewrite (Task 8).
  country?: string;
  source?: string;
}

export function highIncomeExclusionActive(
  f: Pick<BrowseFilters, 'includeHighIncome' | 'incomes'>
): boolean {
  return !f.includeHighIncome && (f.incomes ?? []).length === 0;
}

// v1 semantics: COALESCE keeps 'Unknown' rows visible under the default
// exclusion, and guards a future snapshot regressing to NULL classifications.
const HI_EXCLUDE = "COALESCE(income_group, 'Unknown') != 'High income'";
const IS_HI = "COALESCE(income_group, 'Unknown') = 'High income'";

function inList(col: string, values: string[]): string {
  return `${col} IN (${values.map(sqlQuote).join(', ')})`;
}

function explicitConditions(f: BrowseFilters): string[] {
  const c: string[] = [];
  if (f.countries?.length) c.push(inList('country_code', f.countries));
  if (f.regions?.length) c.push(inList("COALESCE(region, 'Unknown')", f.regions));
  if (f.incomes?.length) c.push(inList("COALESCE(income_group, 'Unknown')", f.incomes));
  if (f.sources?.length) c.push(inList('source', f.sources));
  return c;
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
  const conditions = explicitConditions(f);
  if (!f.includeNonSovereign) conditions.push('is_sovereign = true');
  if (highIncomeExclusionActive(f)) conditions.push(HI_EXCLUDE);
  const where = conditions.length ? `WHERE ${conditions.join(' AND ')}` : '';
  // strftime keeps dates as ISO strings end to end; Arrow JS's Date32
  // representation has varied across versions (Date objects vs epoch-ms).
  return `
    SELECT slug, display_name, issuer_name,
           strftime(publication_date, '%Y-%m-%d') AS publication_date,
           country_name, doc_type, source, is_sovereign
    FROM docs
    ${where}
    ORDER BY publication_date DESC NULLS LAST, slug DESC
    LIMIT ${f.pageSize} OFFSET ${f.page * f.pageSize}
  `;
}

// One aggregate round trip for the scope-status copy: the matching count
// plus the two MARGINAL hidden counts (what each inactive toggle would
// reveal, given every explicit filter). The client maps zeros/inactive
// arms to null before statusLine renders sentences.
export function buildStatusCountsSql(f: BrowseFilters): string {
  const scopeP = f.includeNonSovereign ? 'TRUE' : 'is_sovereign = true';
  const notScope = f.includeNonSovereign ? 'FALSE' : 'is_sovereign IS DISTINCT FROM true';
  const hiActive = highIncomeExclusionActive(f);
  const hiP = hiActive ? HI_EXCLUDE : 'TRUE';
  const isHi = hiActive ? IS_HI : 'FALSE';
  const explicit = explicitConditions(f);
  const where = explicit.length ? `WHERE ${explicit.join(' AND ')}` : '';
  return `
    SELECT
      count(*) FILTER (WHERE ${scopeP} AND ${hiP})::INTEGER AS matching,
      count(*) FILTER (WHERE ${hiP} AND ${notScope})::INTEGER AS hidden_scope,
      count(*) FILTER (WHERE ${scopeP} AND ${isHi})::INTEGER AS hidden_hi
    FROM docs
    ${where}
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

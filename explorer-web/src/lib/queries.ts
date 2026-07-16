// All SQL for the browse page lives here (framework-agnostic; S3 reuses it).
// The client scripts never assemble SQL. Only `import type` from duckdb-wasm
// so no value import enters the vitest graph; this module must never import
// duck.ts (the connection arrives as a parameter).

import type { AsyncDuckDBConnection } from "@duckdb/duckdb-wasm";

export interface BrowseFilters {
  countries: string[];
  regions: string[];
  incomes: string[];
  sources: string[];
  includeNonSovereign: boolean;
  includeHighIncome: boolean;
  page: number; // 0-based internal (1-based only in the URL codec)
  pageSize: number;
  q: string; // free-text find-the-document search; '' means no search
}

export function highIncomeExclusionActive(
  f: Pick<BrowseFilters, "includeHighIncome" | "incomes" | "countries">,
): boolean {
  return (
    !f.includeHighIncome && f.incomes.length === 0 && f.countries.length === 0
  );
}

// v1 semantics: COALESCE keeps 'Unknown' rows visible under the default
// exclusion, and guards a future snapshot regressing to NULL classifications.
const HI_EXCLUDE = "COALESCE(income_group, 'Unknown') != 'High income'";
const IS_HI = "COALESCE(income_group, 'Unknown') = 'High income'";

function inList(col: string, values: string[]): string {
  return `${col} IN (${values.map(sqlQuote).join(", ")})`;
}

// Free-text find-the-document search. The four columns are the human-facing
// identity of a document (what someone types when hunting for one). ESCAPE
// '\' pairs with likeEscape so a term containing %, _, or \ matches literally.
const SEARCH_COLUMNS = [
  "display_name",
  "issuer_name",
  "title",
  "country_name",
] as const;
const MAX_SEARCH_TERMS = 8;

// Escape the LIKE metacharacters (and the escape char itself) so a term is
// matched literally under ILIKE ... ESCAPE '\'. Backslash goes first, or the
// escapes we add would themselves be re-escaped.
export function likeEscape(v: string): string {
  return v
    .replaceAll("\\", "\\\\")
    .replaceAll("%", "\\%")
    .replaceAll("_", "\\_");
}

// Each whitespace-separated term becomes one OR group over SEARCH_COLUMNS;
// terms AND together (each is a separate array element the callers join with
// AND). Empty/whitespace q contributes nothing. Capped at MAX_SEARCH_TERMS so
// a pasted paragraph cannot balloon the SQL.
function searchConditions(q: string): string[] {
  const trimmed = q.trim();
  if (!trimmed) return [];
  return trimmed
    .split(/\s+/)
    .slice(0, MAX_SEARCH_TERMS)
    .map((term) => {
      const pattern = sqlQuote(`%${likeEscape(term)}%`);
      const ors = SEARCH_COLUMNS.map(
        (col) => `${col} ILIKE ${pattern} ESCAPE '\\'`,
      );
      return `(${ors.join(" OR ")})`;
    });
}

function explicitConditions(f: BrowseFilters): string[] {
  const c: string[] = [];
  if (f.countries.length) c.push(inList("country_code", f.countries));
  if (f.regions.length)
    c.push(inList("COALESCE(region, 'Unknown')", f.regions));
  if (f.incomes.length)
    c.push(inList("COALESCE(income_group, 'Unknown')", f.incomes));
  if (f.sources.length) c.push(inList("source", f.sources));
  // SINGLE SEAM: search clauses live here, inside explicitConditions, so every
  // builder (list, status counts, and any future aggregate layered over this
  // WHERE) inherits them by construction rather than re-adding them.
  c.push(...searchConditions(f.q ?? ""));
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

function listWhereClause(f: BrowseFilters): string {
  const conditions = explicitConditions(f);
  if (!f.includeNonSovereign) conditions.push("is_sovereign = true");
  if (highIncomeExclusionActive(f)) conditions.push(HI_EXCLUDE);
  return conditions.length ? `WHERE ${conditions.join(" AND ")}` : "";
}

export function buildListSql(f: BrowseFilters): string {
  // strftime keeps dates as ISO strings end to end; Arrow JS's Date32
  // representation has varied across versions (Date objects vs epoch-ms).
  return `
    SELECT slug, display_name, issuer_name,
           strftime(publication_date, '%Y-%m-%d') AS publication_date,
           country_name, doc_type, source, is_sovereign
    FROM docs
    ${listWhereClause(f)}
    ORDER BY publication_date DESC NULLS LAST, slug DESC
    LIMIT ${f.pageSize} OFFSET ${f.page * f.pageSize}
  `;
}

export function buildExportSql(f: BrowseFilters): string {
  return `
    SELECT slug, display_name, issuer_name, title,
           CASE
             WHEN storage_key IN ('luxse__2175370', 'luxse__2176190')
              AND title = 'Suspension - JHO - THE BOLIVARIAN REPUBLIC OF VENEZUELA - 17.09.2014'
             THEN 'Suspension - JHO - THE BOLIVIAN REPUBLIC OF VENEZUELA - 17.09.2014'
             ELSE NULL
           END AS raw_title,
           strftime(publication_date, '%Y-%m-%d') AS publication_date,
           country_name, region, income_group, doc_type, source,
           is_sovereign, filing_url
    FROM docs
    ${listWhereClause(f)}
    ORDER BY publication_date DESC NULLS LAST, slug DESC
    LIMIT 10001
  `;
}

// One aggregate round trip for the scope-status copy: the matching count
// plus the two MARGINAL hidden counts (what each inactive toggle would
// reveal, given every explicit filter). The client maps zeros/inactive
// arms to null before statusLine renders sentences.
export function buildStatusCountsSql(f: BrowseFilters): string {
  const scopeP = f.includeNonSovereign ? "TRUE" : "is_sovereign = true";
  const notScope = f.includeNonSovereign
    ? "FALSE"
    : "is_sovereign IS DISTINCT FROM true";
  const hiActive = highIncomeExclusionActive(f);
  const hiP = hiActive ? HI_EXCLUDE : "TRUE";
  const isHi = hiActive ? IS_HI : "FALSE";
  const includedHiOverride =
    !f.includeHighIncome && f.countries.length > 0 && f.incomes.length === 0
      ? `count(*) FILTER (WHERE ${scopeP} AND ${IS_HI})`
      : "0";
  const explicit = explicitConditions(f);
  const where = explicit.length ? `WHERE ${explicit.join(" AND ")}` : "";
  return `
    SELECT
      count(*) FILTER (WHERE ${scopeP} AND ${hiP})::INTEGER AS matching,
      count(*) FILTER (WHERE ${hiP} AND ${notScope})::INTEGER AS hidden_scope,
      count(*) FILTER (WHERE ${scopeP} AND ${isHi})::INTEGER AS hidden_hi,
      ${includedHiOverride}::INTEGER AS included_hi_override
    FROM docs
    ${where}
  `;
}

export async function runQuery(
  conn: AsyncDuckDBConnection,
  sql: string,
): Promise<Record<string, unknown>[]> {
  const result = await conn.query(sql);
  return result.toArray().map((row) => row.toJSON() as Record<string, unknown>);
}

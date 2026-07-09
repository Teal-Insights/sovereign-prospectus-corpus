import { expect, it } from 'vitest';

import { buildListSql, createDocsViewSql, sqlQuote } from '../../src/lib/queries';

const DEFAULTS = {
  countries: [],
  regions: [],
  incomes: [],
  sources: [],
  includeNonSovereign: false,
  includeHighIncome: false,
  page: 0,
  pageSize: 50,
  q: '',
};

it('pins the null order and slug tiebreak', () => {
  const sql = buildListSql(DEFAULTS);
  expect(sql).toContain('ORDER BY publication_date DESC NULLS LAST, slug DESC');
});

it('casts dates to ISO strings in SQL (Arrow Date32 representation varies)', () => {
  expect(buildListSql(DEFAULTS)).toContain("strftime(publication_date, '%Y-%m-%d') AS publication_date");
});

it('defaults to sovereign scope and drops the filter when included', () => {
  expect(buildListSql(DEFAULTS)).toContain('is_sovereign = true');
  // is_sovereign stays in the SELECT list (badge column); only the WHERE
  // filter must disappear.
  expect(buildListSql({ ...DEFAULTS, includeNonSovereign: true })).not.toContain('is_sovereign = true');
});

it('escapes filter literals', () => {
  expect(sqlQuote("Cote d'Ivoire")).toBe("'Cote d''Ivoire'");
  const sql = buildListSql({ ...DEFAULTS, countries: ["CIV", "KE'N"] });
  expect(sql).toContain("country_code IN ('CIV', 'KE''N')");
});

it('paginates with LIMIT/OFFSET arithmetic', () => {
  const sql = buildListSql({ ...DEFAULTS, page: 3, pageSize: 25 });
  expect(sql).toContain('LIMIT 25 OFFSET 75');
});

it('docs view bootstrap SQL lives here (single named contract)', () => {
  expect(createDocsViewSql('documents.parquet')).toBe(
    "CREATE OR REPLACE VIEW docs AS SELECT * FROM read_parquet('documents.parquet')"
  );
});

// ---- S3 additions (TEA-903): multi-select filters, interplay rule, status counts ----
import { buildStatusCountsSql, highIncomeExclusionActive } from '../../src/lib/queries';

it('high-income exclusion truth table', () => {
  expect(highIncomeExclusionActive({ includeHighIncome: false, incomes: [] })).toBe(true);
  expect(highIncomeExclusionActive({ includeHighIncome: true, incomes: [] })).toBe(false);
  expect(highIncomeExclusionActive({ includeHighIncome: false, incomes: ['Low income'] })).toBe(false);
  expect(highIncomeExclusionActive({ includeHighIncome: true, incomes: ['High income'] })).toBe(false);
});

it('default list SQL excludes high income with a COALESCE null guard', () => {
  const sql = buildListSql(DEFAULTS);
  expect(sql).toContain("COALESCE(income_group, 'Unknown') != 'High income'");
});

it('explicit income selections drop the high-income exclusion (interplay rule)', () => {
  const sql = buildListSql({ ...DEFAULTS, incomes: ['High income'] });
  expect(sql).not.toContain("!= 'High income'");
  expect(sql).toContain("COALESCE(income_group, 'Unknown') IN ('High income')");
});

it('includeHighIncome drops the exclusion without an income selection', () => {
  const sql = buildListSql({ ...DEFAULTS, includeHighIncome: true });
  expect(sql).not.toContain("!= 'High income'");
});

it('region filters use the Unknown COALESCE guard', () => {
  const sql = buildListSql({ ...DEFAULTS, regions: ['Sub-Saharan Africa', 'Unknown'] });
  expect(sql).toContain("COALESCE(region, 'Unknown') IN ('Sub-Saharan Africa', 'Unknown')");
});

it('source filter uses raw keys', () => {
  expect(buildListSql({ ...DEFAULTS, sources: ['edgar', 'nsm'] })).toContain(
    "source IN ('edgar', 'nsm')"
  );
});

it('status counts SQL: three FILTER arms with explicit filters in the outer WHERE', () => {
  const sql = buildStatusCountsSql({ ...DEFAULTS, countries: ['KEN'] });
  expect(sql).toContain("WHERE country_code IN ('KEN')");
  expect(sql).toContain('FILTER (WHERE is_sovereign = true AND');
  expect(sql).toContain('is_sovereign IS DISTINCT FROM true');
  expect(sql).toContain("COALESCE(income_group, 'Unknown') = 'High income'");
  expect(sql).toContain('::INTEGER AS matching');
  expect(sql).toContain('::INTEGER AS hidden_scope');
  expect(sql).toContain('::INTEGER AS hidden_hi');
});

it('status counts arms flip to TRUE/FALSE when a toggle is inactive', () => {
  const allIn = buildStatusCountsSql({
    ...DEFAULTS,
    includeNonSovereign: true,
    includeHighIncome: true,
  });
  expect(allIn).toContain('FILTER (WHERE TRUE AND TRUE)::INTEGER AS matching');
  expect(allIn).toContain('FILTER (WHERE TRUE AND FALSE)::INTEGER AS hidden_scope');
  expect(allIn).toContain('FILTER (WHERE TRUE AND FALSE)::INTEGER AS hidden_hi');
});

// ---- B2 additions (TEA-930): find-the-document search on browse ----
import { likeEscape } from '../../src/lib/queries';

// One search term expands to an OR over the four indexed text columns, each
// ILIKE guarded by ESCAPE '\' so likeEscape's backslash escapes are honored.
const grp = (t: string): string =>
  `(display_name ILIKE '%${t}%' ESCAPE '\\' OR issuer_name ILIKE '%${t}%' ESCAPE '\\' ` +
  `OR title ILIKE '%${t}%' ESCAPE '\\' OR country_name ILIKE '%${t}%' ESCAPE '\\')`;

const count = (haystack: string, needle: string): number => haystack.split(needle).length - 1;

it('likeEscape neutralizes LIKE wildcards and the escape char itself', () => {
  expect(likeEscape('100%')).toBe('100\\%');
  expect(likeEscape('a_b')).toBe('a\\_b');
  expect(likeEscape('a\\b')).toBe('a\\\\b');
  expect(likeEscape('plain')).toBe('plain');
  // backslash is escaped first so a literal `\%` in the term does not become
  // an escape sequence in the pattern.
  expect(likeEscape('\\%')).toBe('\\\\\\%');
});

it('a single search term hits all four text columns as an OR group', () => {
  const sql = buildListSql({ ...DEFAULTS, q: 'Philippines' });
  expect(sql).toContain(grp('Philippines'));
  // spelled out so the exact string is pinned independent of the helper
  expect(sql).toContain(
    "(display_name ILIKE '%Philippines%' ESCAPE '\\' " +
      "OR issuer_name ILIKE '%Philippines%' ESCAPE '\\' " +
      "OR title ILIKE '%Philippines%' ESCAPE '\\' " +
      "OR country_name ILIKE '%Philippines%' ESCAPE '\\')"
  );
});

it('two terms AND together (Philippines 2031 narrows in two words)', () => {
  const sql = buildListSql({ ...DEFAULTS, q: 'Philippines 2031' });
  expect(sql).toContain(`${grp('Philippines')} AND ${grp('2031')}`);
});

it("apostrophes in a term are escaped by sqlQuote (O'Higgins)", () => {
  const sql = buildListSql({ ...DEFAULTS, q: "O'Higgins" });
  expect(sql).toContain("ILIKE '%O''Higgins%' ESCAPE '\\'");
});

it('% and _ in a term are neutralized by likeEscape', () => {
  const sql = buildListSql({ ...DEFAULTS, q: '20%_A' });
  expect(sql).toContain("'%20\\%\\_A%'");
});

it('at most 8 terms are searched (9 terms truncate to 8)', () => {
  const sql = buildListSql({ ...DEFAULTS, q: 't1 t2 t3 t4 t5 t6 t7 t8 t9' });
  expect(count(sql, 'country_name ILIKE')).toBe(8);
  expect(sql).toContain("'%t8%'");
  expect(sql).not.toContain("'%t9%'");
});

it('whitespace-only or empty q contributes no search clause', () => {
  expect(buildListSql({ ...DEFAULTS, q: '   ' })).not.toContain('ILIKE');
  expect(buildListSql(DEFAULTS)).not.toContain('ILIKE');
  // an all-whitespace q builds byte-identical SQL to no q at all
  expect(buildListSql({ ...DEFAULTS, q: '  \t ' })).toBe(buildListSql(DEFAULTS));
});

it('the counts SQL carries the same search clauses (single seam)', () => {
  const sql = buildStatusCountsSql({ ...DEFAULTS, q: 'bond' });
  expect(sql).toContain(`WHERE ${grp('bond')}`);
});

it('search clauses AND with explicit filters in the counts WHERE', () => {
  const sql = buildStatusCountsSql({ ...DEFAULTS, countries: ['KEN'], q: 'bond' });
  expect(sql).toContain(`WHERE country_code IN ('KEN') AND ${grp('bond')}`);
});

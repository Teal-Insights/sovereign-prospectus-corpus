import { expect, it } from 'vitest';

import {
  buildCountSql,
  buildDistinctSql,
  buildListSql,
  buildScopeCountsSql,
  sqlQuote,
} from '../../src/lib/queries';

const DEFAULTS = { includeNonSovereign: false, page: 0, pageSize: 50 };

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
  const sql = buildListSql({ ...DEFAULTS, country: "Cote d'Ivoire" });
  expect(sql).toContain("country_name = 'Cote d''Ivoire'");
});

it('paginates with LIMIT/OFFSET arithmetic', () => {
  const sql = buildListSql({ ...DEFAULTS, page: 3, pageSize: 25 });
  expect(sql).toContain('LIMIT 25 OFFSET 75');
});

it('count SQL matches the same filters and casts to INTEGER', () => {
  const sql = buildCountSql({ ...DEFAULTS, source: 'nsm' });
  expect(sql).toContain('count(*)::INTEGER');
  expect(sql).toContain("source = 'nsm'");
  expect(sql).toContain('is_sovereign = true');
});

it('scope counts cast to INTEGER and cover the three states', () => {
  const sql = buildScopeCountsSql();
  expect(sql).toContain('::INTEGER');
  expect(sql).toContain('is_sovereign = true');
});

it('distinct SQL excludes NULLs and sorts', () => {
  const sql = buildDistinctSql('country_name');
  expect(sql).toContain('DISTINCT');
  expect(sql).toContain('country_name IS NOT NULL');
  expect(sql).toContain('ORDER BY');
});

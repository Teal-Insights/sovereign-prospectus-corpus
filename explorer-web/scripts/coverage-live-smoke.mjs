// Target-specific release acceptance for the July 2026 coverage patch batch.
//
// Usage:
//   BASE=https://prospectus.tealinsights.com \
//   DATA_BASE=https://data.tealinsights.com/prospectus/snapshot \
//   node scripts/coverage-live-smoke.mjs

import { asyncBufferFromUrl, parquetReadObjects } from "hyparquet";

const BASE = (
  process.env.BASE ?? "https://prospectus.tealinsights.com"
).replace(/\/+$/, "");
const DATA_BASE = (
  process.env.DATA_BASE ?? "https://data.tealinsights.com/prospectus/snapshot"
).replace(/\/+$/, "");

const expectedEdgar = new Set([
  "edgar-0000950133-04-000030",
  "edgar-0000950133-04-000398",
  "edgar-0000950133-04-003572",
  "edgar-0000950133-04-003653",
  "edgar-0000950133-04-003735",
  "edgar-0000950133-04-004528",
  "edgar-0000950133-04-004556",
  "edgar-0000950133-05-000954",
]);
const expectedBolivia = new Set([
  "luxse-102752130",
  "luxse-102761291",
  "luxse-102771545",
  "luxse-102774687",
  "luxse-102775400",
  "luxse-102803082",
  "luxse-105422819",
  "luxse-1651746",
  "luxse-1791640",
  "luxse-3138724",
]);
const expectedLse = new Set([
  "lse-therepublicofcongo-us6700000009875amortisingnotesdue2032",
  "lse-therepublicofcongo-xz57",
  "lse-therepublicofcongo-yk35",
]);
const correctedNoticeSlugs = new Set(["luxse-2175370", "luxse-2176190"]);
const rawTitle =
  "Suspension - JHO - THE BOLIVIAN REPUBLIC OF VENEZUELA - 17.09.2014";
const correctedTitle =
  "Suspension - JHO - THE BOLIVARIAN REPUBLIC OF VENEZUELA - 17.09.2014";

const checks = [];
function check(name, condition, detail) {
  checks.push({ name, pass: Boolean(condition), detail });
}
function sameSet(actual, expected) {
  return (
    actual.size === expected.size &&
    [...expected].every((value) => actual.has(value))
  );
}
function search(rows, term) {
  const needle = term.toLowerCase();
  return rows.filter((row) =>
    [row.display_name, row.issuer_name, row.title, row.country_name].some(
      (value) =>
        String(value ?? "")
          .toLowerCase()
          .includes(needle),
    ),
  );
}

const manifestResponse = await fetch(`${DATA_BASE}/MANIFEST.json`, {
  cache: "no-store",
});
check(
  "manifest HTTP",
  manifestResponse.ok,
  `status=${manifestResponse.status}`,
);
const manifest = await manifestResponse.json();
check(
  "schema v1",
  manifest.schema_version === 1,
  `schema=${manifest.schema_version}`,
);
check(
  "document count",
  manifest.document_count === 9795,
  `count=${manifest.document_count}`,
);
check(
  "source counts",
  JSON.stringify(manifest.documents_by_source) ===
    JSON.stringify({ edgar: 3339, lse: 3, luxse: 4965, nsm: 665, pdip: 823 }),
  JSON.stringify(manifest.documents_by_source),
);

const parquet = await asyncBufferFromUrl(
  `${DATA_BASE}/documents.parquet?v=${encodeURIComponent(manifest.generated_at)}`,
);
const rows = await parquetReadObjects({ file: parquet });
check("parquet row count", rows.length === 9795, `rows=${rows.length}`);

const slugs = new Set(rows.map((row) => String(row.slug)));
check(
  "eight Venezuela EDGAR additions",
  [...expectedEdgar].every((slug) => slugs.has(slug)),
  [...expectedEdgar].filter((slug) => !slugs.has(slug)).join(",") ||
    "all present",
);
const boliviaRows = rows.filter((row) => row.country_name === "Bolivia");
check(
  "ten Bolivia documents",
  sameSet(new Set(boliviaRows.map((row) => String(row.slug))), expectedBolivia),
  `count=${boliviaRows.length}`,
);
const lseRows = rows.filter((row) => row.source === "lse");
check(
  "three Republic of Congo LSE documents",
  sameSet(new Set(lseRows.map((row) => String(row.slug))), expectedLse),
  `count=${lseRows.length}`,
);
check(
  "Republic of Congo and DRC remain distinct",
  rows.filter((row) => row.country_name === "Republic of Congo").length === 6 &&
    rows.filter(
      (row) => row.country_name === "Democratic Republic of the Congo",
    ).length === 2,
  `COG=${rows.filter((row) => row.country_name === "Republic of Congo").length},COD=${rows.filter((row) => row.country_name === "Democratic Republic of the Congo").length}`,
);

const normalizedRows = rows.filter((row) =>
  correctedNoticeSlugs.has(String(row.slug)),
);
check(
  "two titles normalized with raw provenance",
  normalizedRows.length === 2 &&
    normalizedRows.every(
      (row) => row.title === correctedTitle && row.raw_title === rawTitle,
    ),
  `count=${normalizedRows.length}`,
);
const boliviaSearch = search(rows, "Bolivia");
const venezuelaSearch = search(rows, "Venezuela");
const venezuelaCountryRows = rows.filter(
  (row) => row.country_name === "Venezuela",
);
check(
  "Bolivia search excludes Venezuela notices",
  boliviaSearch.length === 10 &&
    boliviaSearch.every((row) => !correctedNoticeSlugs.has(String(row.slug))),
  `count=${boliviaSearch.length}`,
);
check(
  "Venezuela country coverage and search include corrected notices",
  venezuelaCountryRows.length === 107 &&
    venezuelaSearch.length === 108 &&
    [...correctedNoticeSlugs].every((slug) =>
      venezuelaSearch.some((row) => row.slug === slug),
    ) &&
    venezuelaSearch.some((row) => row.slug === "pdip-ven77"),
  `country=${venezuelaCountryRows.length},search=${venezuelaSearch.length}`,
);

for (const row of lseRows) {
  check(
    `${row.slug} has text`,
    row.has_text === true,
    `has_text=${row.has_text}`,
  );
  const textResponse = await fetch(
    `${DATA_BASE}/text/${row.slug}.json?v=${encodeURIComponent(manifest.generated_at)}`,
  );
  check(
    `${row.slug} text HTTP`,
    textResponse.ok,
    `status=${textResponse.status}`,
  );
  const filingResponse = await fetch(String(row.filing_url), {
    headers: { Range: "bytes=0-3" },
  });
  check(
    `${row.slug} source archive resolves`,
    filingResponse.ok,
    `status=${filingResponse.status}`,
  );
}

const homeResponse = await fetch(`${BASE}/`);
const homeHtml = await homeResponse.text();
check("site home HTTP", homeResponse.ok, `status=${homeResponse.status}`);
check(
  "build stamp matches data generation",
  homeHtml.includes(`data-build-generated-at="${manifest.generated_at}"`),
  `generated_at=${manifest.generated_at}`,
);
const lseDocResponse = await fetch(`${BASE}/doc/lse-therepublicofcongo-xz57/`);
const lseDocHtml = await lseDocResponse.text();
check("LSE detail HTTP", lseDocResponse.ok, `status=${lseDocResponse.status}`);
check(
  "friendly LSE source label",
  lseDocHtml.includes("London Stock Exchange"),
  "detail source label",
);
const normalizedDocResponse = await fetch(`${BASE}/doc/luxse-2175370/`);
const normalizedDocHtml = await normalizedDocResponse.text();
check(
  "raw source title visible on detail",
  normalizedDocResponse.ok &&
    normalizedDocHtml.includes("Raw source title") &&
    normalizedDocHtml.includes("BOLIVIAN REPUBLIC"),
  `status=${normalizedDocResponse.status}`,
);

const failures = checks.filter((item) => !item.pass);
console.log(
  JSON.stringify(
    { status: failures.length ? "fail" : "pass", checks, failures },
    null,
    2,
  ),
);
if (failures.length) process.exit(1);

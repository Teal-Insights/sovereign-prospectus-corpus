import { expect, it } from "vitest";

import { toCsv, type ExportRow } from "../../src/lib/csv";

const HEADER =
  "publication_date,issuer,display_name,title,raw_title,country,region,income_group,doc_type,source,is_sovereign,document_url,filing_url";

const ROW: ExportRow = {
  slug: "sample-document",
  display_name: "Republic of Example 2030",
  issuer_name: "Republic of Example",
  title: "Offering Circular",
  raw_title: null,
  publication_date: "2026-07-10",
  country_name: "Example",
  region: "Example Region",
  income_group: "Middle income",
  doc_type: "Prospectus",
  source: "edgar",
  is_sovereign: true,
  filing_url: "https://filings.example/document",
};

it("serializes a plain row with the specified columns and CRLF separator", () => {
  const result = toCsv([ROW], "https://prospectus.example");

  expect(result).toEqual({
    csv:
      `${HEADER}\r\n` +
      "2026-07-10,Republic of Example,Republic of Example 2030,Offering Circular,,Example," +
      "Example Region,Middle income,Prospectus,edgar,true," +
      "https://prospectus.example/doc/sample-document/,https://filings.example/document",
    truncated: false,
  });
});

it("quotes a field containing a comma", () => {
  const { csv } = toCsv(
    [{ ...ROW, title: "Bonds, Series A" }],
    "https://prospectus.example",
  );

  expect(csv).toContain('"Bonds, Series A"');
});

it("quotes a field containing a quote and doubles the embedded quote", () => {
  const { csv } = toCsv(
    [{ ...ROW, title: 'The "Notes"' }],
    "https://prospectus.example",
  );

  expect(csv).toContain('"The ""Notes"""');
});

it("quotes a field containing a newline", () => {
  const { csv } = toCsv(
    [{ ...ROW, title: "First line\nSecond line" }],
    "https://prospectus.example",
  );

  expect(csv).toContain('"First line\nSecond line"');
});

it("serializes null values as empty strings", () => {
  const { csv } = toCsv(
    [
      {
        slug: "empty-document",
        display_name: null,
        issuer_name: null,
        title: null,
        raw_title: null,
        publication_date: null,
        country_name: null,
        region: null,
        income_group: null,
        doc_type: null,
        source: null,
        is_sovereign: null,
        filing_url: null,
      },
    ],
    "https://prospectus.example",
  );

  expect(csv).toBe(
    `${HEADER}\r\n,,,,,,,,,,,https://prospectus.example/doc/empty-document/,`,
  );
  expect(csv).not.toContain("null");
});

it("drops the 10001st row and reports truncation", () => {
  const rows = Array.from({ length: 10001 }, (_, index) => ({
    ...ROW,
    slug: `document-${index + 1}`,
  }));

  const result = toCsv(rows, "https://prospectus.example");

  expect(result.truncated).toBe(true);
  expect(result.csv.split("\r\n")).toHaveLength(10001);
  expect(result.csv).toContain("/doc/document-10000/");
  expect(result.csv).not.toContain("/doc/document-10001/");
});

it("builds each document URL from the site origin and slug", () => {
  const { csv } = toCsv(
    [{ ...ROW, slug: "edgar-0001" }],
    "https://prospectus.example",
  );

  expect(csv).toContain(",https://prospectus.example/doc/edgar-0001/,");
});

it("normalizes a trailing slash in the site origin", () => {
  const { csv } = toCsv(
    [{ ...ROW, slug: "edgar-0001" }],
    "https://prospectus.example/",
  );

  expect(csv).toContain(",https://prospectus.example/doc/edgar-0001/,");
  expect(csv).not.toContain("prospectus.example//doc");
});

it("prefixes a leading = so a spreadsheet does not evaluate the cell as a formula", () => {
  const { csv } = toCsv(
    [{ ...ROW, title: "=1+1" }],
    "https://prospectus.example",
  );

  expect(csv).toContain(",'=1+1,");
  expect(csv).not.toContain(",=1+1,");
});

it("guards every spreadsheet formula-trigger prefix (= + - @ tab CR)", () => {
  for (const prefix of ["=", "+", "-", "@", "\t", "\r"]) {
    const { csv } = toCsv(
      [{ ...ROW, issuer_name: `${prefix}danger` }],
      "https://prospectus.example",
    );

    expect(csv).toContain(`'${prefix}danger`);
  }
});

it("quotes and guards a formula field that also contains a comma", () => {
  const { csv } = toCsv(
    [{ ...ROW, title: "=SUM(A1,A2)" }],
    "https://prospectus.example",
  );

  expect(csv).toContain(`"'=SUM(A1,A2)"`);
});

it("leaves an ordinary leading character untouched (no spurious guard quote)", () => {
  const { csv } = toCsv(
    [{ ...ROW, title: "Bonds 2031" }],
    "https://prospectus.example",
  );

  expect(csv).toContain(",Bonds 2031,");
  expect(csv).not.toContain("'Bonds");
});

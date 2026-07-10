export interface ExportRow {
  slug: string;
  display_name: string | null;
  issuer_name: string | null;
  title: string | null;
  publication_date: string | null;
  country_name: string | null;
  region: string | null;
  income_group: string | null;
  doc_type: string | null;
  source: string | null;
  is_sovereign: boolean | null;
  filing_url: string | null;
}

const HEADER = [
  'publication_date',
  'issuer',
  'display_name',
  'title',
  'country',
  'region',
  'income_group',
  'doc_type',
  'source',
  'is_sovereign',
  'document_url',
  'filing_url',
];

// Neutralize spreadsheet formula injection (OWASP CSV injection). title,
// issuer_name, and display_name originate from third-party issuer filings
// (EDGAR / NSM / RNS), so a cell whose value begins with = + - @ (or a tab or
// carriage return) could be evaluated as a live formula when the file is opened
// in Excel or Google Sheets. Prefixing a single quote forces text
// interpretation: the spreadsheet hides the quote and shows the true value, so
// the guard preserves on-screen fidelity better than leaving a formula to be
// evaluated. It touches only cells that would otherwise be read as a formula
// (rare in this corpus) and only in the export artifact, never the corpus
// itself. See TEA-936 / #116.
function csvField(value: string | boolean | null): string {
  if (value === null) return '';
  const raw = String(value);
  const guarded = /^[=+\-@\t\r]/.test(raw) ? `'${raw}` : raw;
  return /[",\r\n]/.test(guarded) ? `"${guarded.replaceAll('"', '""')}"` : guarded;
}

export function toCsv(
  rows: ExportRow[],
  siteOrigin: string
): { csv: string; truncated: boolean } {
  const cleanOrigin = siteOrigin.replace(/\/+$/, '');
  const truncated = rows.length === 10001;
  const exportedRows = truncated ? rows.slice(0, 10000) : rows;
  const records = exportedRows.map((row) =>
    [
      row.publication_date,
      row.issuer_name,
      row.display_name,
      row.title,
      row.country_name,
      row.region,
      row.income_group,
      row.doc_type,
      row.source,
      row.is_sovereign,
      `${cleanOrigin}/doc/${row.slug}/`,
      row.filing_url,
    ]
      .map(csvField)
      .join(',')
  );

  return { csv: [HEADER.join(','), ...records].join('\r\n'), truncated };
}

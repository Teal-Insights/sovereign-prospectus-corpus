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

function csvField(value: string | boolean | null): string {
  if (value === null) return '';
  const text = String(value);
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
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

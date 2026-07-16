# Republic of Congo LSE verification ledger

Date: 2026-07-15 America/New_York

Issue: TEA-1005

Issuer page: <https://www.londonstockexchange.com/stock/XZ57/the-republic-of-congo/company-page>

## Result

The official LSE issuer metadata identifies `TREPCG` as `THE REPUBLIC OF
CONGO`, country of incorporation `CG`, with three listed instruments: `YK35`,
`XP53`, and `XZ57`. This is the Republic of Congo (`COG`), not the Democratic
Republic of the Congo (`COD`).

Four issuance events were inventoried. The checked official LSE/LSEG API
surfaces expose three distinct offering circulars. The February 2026 private
placement, instrument `XP53` and ISIN `XS3295059367`, has no
`tradingDocument` link in the official instrument component and no artifact in
the checked instrument-document or programme endpoints. This is a bounded API
result, not a claim that no document exists elsewhere. No fourth document was
inferred or created.

| Event | LSE instrument | Public legal artifact | Disposition |
| --- | --- | --- | --- |
| 2025-11-07, US$670m 9.875% due 2032 | YK35 / XS3223166409 | Final offering circular dated 2025-11-05 | Ingest |
| 2025-12-19, US$260m tap | YK35 / XS3223166409 | Final offering circular dated 2025-12-17 | Ingest in the 2032 family |
| 2026-02-19, US$700m placement and tender | XP53 / XS3295059367 | No artifact on the checked official LSE component, instrument-document, or programme API surfaces | Record the bounded API result; do not infer that no document exists elsewhere |
| 2026-05-26, US$850m 9.500% due 2036 | XZ57 / XS3376882687 | Final offering circular dated 2026-05-22 | Ingest |

## Artifact verification

All checks were performed on the host before canonical ingestion. Each file
begins with the four bytes `%PDF`, opens in both Poppler and PyMuPDF, has
nonzero pages and nonempty text, and names `THE REPUBLIC OF CONGO` on the cover.

The machine inventory also pins each official ZIP archive's SHA-256, byte
size, and sole member name. The helper requires the archive URL basename to
match the native document ID and proves the promoted PDF bytes equal that
archived member.

| Native ID | Role | Pages | Bytes | SHA-256 |
| --- | --- | ---: | ---: | --- |
| `THEREPUBLICOFCONGO-US6700000009875AmortisingNotesdue2032` | Base | 178 | 2,273,130 | `e2236200ec7ec7f302cda0dc0170f0b047326eb67f9a1b4b4310a5554fbf24d8` |
| `THEREPUBLICOFCONGO-YK35` | Tap | 178 | 2,282,219 | `3f4682e2efaa2e37dcace466f1714e13e25ed420ac9c9f4bdbe97c79a9eb9e9d` |
| `THEREPUBLICOFCONGO-XZ57` | Standalone | 183 | 2,141,624 | `a5e4576e4ca101c18a1d21191e82b7cccc8f523b7aec6b7525f6ea318becbc60` |

The three hashes are distinct. The machine-readable association and expected
artifact values are in
`docs/reports/2026-07-15-lse-congo-inventory.json`.

## Retrieval trail

The public page is an Angular shell. Host-side retrieval used the official LSE
page handshake and component refresh endpoints to obtain issuer, instrument,
programme, and trading-document metadata. The returned issuer-services asset
URLs were downloaded directly. The programme endpoint returned the November
archive; the instrument components returned December `YK35` and May `XZ57`
archives, while `XP53` returned no trading-document URL.

The negative XP53 result was independently rechecked on 2026-07-16 at 02:53
UTC. The successful component request was `POST
https://api.londonstockexchange.com/api/v1/components/refresh` with path
`issuer-profile`, parameters
`tidm%3DXP53%26issuername%3Dthe-republic-of-congo%26tabId%3D771b9c49-382e-4e74-bd94-e96af5c94285`,
and component ID
`block_content%3Aeb11eb09-4797-469c-a6ca-a258d2a53d60`. The response identified
XP53, ISIN `XS3295059367`, issuer `TREPCG`, and admission date `2026-02-19`,
with `tradingDocument: null`. `GET
https://cache-api.lsegissuerservices.com/documents/TREPCG/XP53` returned HTTP
200 with JSON `null`; `GET
https://cache-api.lsegissuerservices.com/documents/TREPCG/programmes` returned
only the November 2032 programme archive.

The bounded helper `scripts/build_lse_manual_manifest.py` validates the review
ledger, archive identity and contents, PDF magic bytes, SHA-256, size, page count, and nonempty PyMuPDF text
before it writes any document or manifest record. It atomically reconciles the
canonical `lse_manifest.jsonl` and refuses hash conflicts or duplicate legal
artifacts.

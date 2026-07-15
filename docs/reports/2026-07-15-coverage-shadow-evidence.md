# Coverage patch shadow-run evidence

Status: pre-release evidence only. This run used an isolated shadow copy of the
canonical database. It did not change canonical data or a published snapshot.

Pipeline revision: `00655a6`

## Reconciliation

| Source | Selector | Discovered | Downloaded | Parsed | Pages | Bytes | Manifest SHA-256 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| EDGAR | CIK `0000103198` | 8 | 8 | 8 | 590 | 4,889,188 | `ae2976e071b3eafaccf07320bf02ff9ea48e497586aa05c314aee7f764185ecd` |
| LuxSE | exact issuer `BOLIVIA (PLURINATIONAL STATE OF)`, issuer ID `29689` | 10 | 10 | 10 | 950 | 15,271,484 | `5a4c1b15b43ecdc4fdf9b6932f48abfc3a69cdb7ac50712bf71f5f289f53d33e` |

Both download commands were rerun. The second run downloaded zero files,
skipped every selected file, and left each manifest hash unchanged. All 18
parses had `parse_status = parse_ok` and at least one nonempty page.

## Document ledger

| Source | Native ID | Date | Type | Bytes | Pages | File SHA-256 |
| --- | --- | --- | --- | ---: | ---: | --- |
| EDGAR | `0000950133-05-000954` | 2005-03-09 | 424B5 | 298,516 | 57 | `687db0776ec72ef351b9d34ce3bfa5a7d2569c14ecf3bd739bcc31b3c2dca3a2` |
| EDGAR | `0000950133-04-004556` | 2004-12-10 | 424B3 | 1,922 | 2 | `5cda3b907db7b778bdb191806d637cae91af345220e904901df5280e1a804be5` |
| EDGAR | `0000950133-04-004528` | 2004-12-08 | 424B5 | 243,163 | 48 | `823be3ac177ebe416219ff4bf3bd7ad6489b29dfc105ede6b286321ba5e29600` |
| EDGAR | `0000950133-04-003735` | 2004-10-08 | 424B3 | 3,486 | 2 | `b60ed24798696429fa7bcaafbed15cadcbbce61795868eed933c8771aa2003e1` |
| EDGAR | `0000950133-04-003653` | 2004-10-01 | 424B5 | 308,636 | 62 | `f8ddabc221c6145960991b1559948b3cd8ff8a986827e79e439d39f4b8db9cf4` |
| EDGAR | `0000950133-04-003572` | 2004-09-23 | 424B5 | 412,417 | 85 | `44360c78c88a96a72c76e267ff4491c3c6e9cbc5832d0b04ef70caa7feee3593` |
| EDGAR | `0000950133-04-000398` | 2004-02-12 | 424B5 | 1,852,956 | 177 | `238f2c540b55b62b5d6de9b1e46bf770a9c73a2d5a89395b95a6a19d1eb88377` |
| EDGAR | `0000950133-04-000030` | 2004-01-09 | 424B5 | 1,768,092 | 157 | `397eeba78073fbff45027c2aa0f62788aa1e8e2e1a310f57059837733fa77565` |
| LuxSE | `1651746` | 2012-10-21 | D010 | 1,689,438 | 167 | `ca68f682604f54916c5314f6a5111865d26ccd5e870f54307baab7588b822d1d` |
| LuxSE | `1791640` | 2013-08-21 | D010 | 2,216,054 | 165 | `e588aca9de504c54ecc3e770aa195bdde8a67d5bf28c58e752fd8551fcf849de` |
| LuxSE | `3138724` | 2017-03-22 | D010 | 2,756,392 | 168 | `9e00467b45530e15eec2698b1b928a22c3ba59448d59a4ad27506c60e4bfc050` |
| LuxSE | `102752130` | 2022-02-10 | D455 | 315,907 | 6 | `6eded8fbba6be9c186fb1c3c8e04223cfded6798b5af249883eda36b1a013bbf` |
| LuxSE | `102761291` | 2022-02-16 | D455 | 316,169 | 5 | `77c8b25771b58a16bd8ebbbbd0c76e7a60969095ba1f0f6c53f0d2234ff21384` |
| LuxSE | `102771545` | 2022-02-22 | D455 | 131,789 | 3 | `fbbc72928db3153c43f8c03f260a4f3783e5fb831d98c65e560a40743612a29e` |
| LuxSE | `102774687` | 2022-02-23 | D455 | 136,015 | 4 | `8acef4ea15a1fa29a4d8287777e2732b0f6e2145e229a4782c27143f070c38ff` |
| LuxSE | `102775400` | 2022-02-24 | D455 | 141,299 | 4 | `fe53d8f26464348e51b1c4e521622af92c1c7eb325ed96091d1c97d2228c8884` |
| LuxSE | `102803082` | 2022-03-09 | D010 | 4,018,307 | 206 | `76c051ab6f08147ebefe008db30127829c21ee10def7445661e3720bf52c45fb` |
| LuxSE | `105422819` | 2026-06-03 | D010 | 3,550,114 | 222 | `7f8b78e44fc0532c3dfd7f2b4b94e74c95f31af7119cb29679fc18c9ed5c0c74` |

## Provenance and audit assertions

- The SEC submissions response identified the issuer as `BOLIVARIAN REPUBLIC
  OF VENEZUELA`; every EDGAR record preserved CIK `0000103198`, accession
  number, form type, and primary document.
- The LuxSE issuer lookup resolved exactly one native issuer: ID `29689` and
  name `BOLIVIA (PLURINATIONAL STATE OF)`. All 10 document complements yielded
  that exact issuer name.
- The requested Bolivia anchors are document `105422819` for ISIN
  `US29731QAF46` and document `3138724` for ISIN `USP37878AC26`.
- After ingest and full-text index rebuild, the shadow database contained 10
  Bolivia documents and 107 Venezuela documents. Venezuela comprised 60 LuxSE,
  39 PDIP, and 8 EDGAR documents.
- The country audit found zero Bolivia records attributed to Venezuela and zero
  Venezuela records attributed to Bolivia.

Stable LuxSE security pages used to identify the anchors:

- `https://www.luxse.com/security/US29731QAF46/531937`
- `https://www.luxse.com/security/USP37878AC26/248958`

The shadow workspace was `/tmp/coverage-data-20260715`. This ledger is the
durable inventory; the workspace itself is not a release input.

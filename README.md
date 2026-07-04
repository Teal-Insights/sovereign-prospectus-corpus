# Searching the Fine Print (at Scale)

An open source pipeline for extracting and searching contract terms from sovereign bond prospectuses. Built on the expert annotations from [#PublicDebtIsPublic](https://publicdebtispublic.mdi.georgetown.edu/).

## What this does

1. **Downloads** sovereign bond prospectuses from SEC EDGAR, FCA National Storage Mechanism, and the PDIP corpus
2. **Locates** likely clause sections using deterministic pattern matching
3. **Extracts** clauses using LLMs with multi-shot prompts derived from PDIP's expert-annotated contracts
4. **Verifies** every extraction against the source text (95% verbatim match threshold)

The result: **9,145 potential clause matches** across **59 countries** and 6 clause families (collective action clauses, pari passu, governing law, sovereign immunity, negative pledge, events of default) from **4,800+ documents**.

These are potential matches, not validated findings. Validation requires expert legal review.

## Why

Sovereign debt legal expertise is scarce and expensive. The contract terms that govern how nations borrow, restructure, and default are buried in dense prospectuses. This pipeline narrows thousands of documents down to a manageable set of likely matches so lawyers can focus their time on judgment, not search.

## The proposal

This project was presented at the [#PublicDebtIsPublic Infrastructure Scoping Roundtable](https://publicdebtispublic.mdi.georgetown.edu/) on March 30, 2026 at Georgetown University Law Center. The accompanying proposal is available as a [Quarto book](https://teal-insights.github.io/sovereign-prospectus-corpus/).

## Quick start

```bash
git clone https://github.com/Teal-Insights/sovereign-prospectus-corpus.git
cd sovereign-prospectus-corpus
uv sync
uv run pytest -v
```

## Static snapshot for the web explorer

The web explorer consumes a static snapshot generated from the corpus database:

```bash
uv run python scripts/build_snapshot.py
```

This reads `data/db/corpus.duckdb` (read-only) and writes to `data/snapshot/`:

| Component | Contents |
|---|---|
| `documents.parquet` | One row per document: stable URL slug, issuer, country, region, income group (World Bank classifications), source, publication date, document type, original-filing URL, text availability |
| `text/<slug>.json` | Per-document full text (Docling markdown, with per-page text as fallback) plus a table-of-contents structure derived from markdown headings, with character offsets. Offsets are Unicode code point indices into `text` (JavaScript consumers using UTF-16 string indexing must convert). Plain JSON, gzip-friendly |
| `MANIFEST.json` | Snapshot date, document counts by source, schema version, component sizes |

Slugs are derived from the pipeline's stable storage keys (`{source}__{native_id}`, e.g. `nsm__101126915` becomes `nsm-101126915`) and are safe to use in URLs. Options: `--db-path`, `--output-dir`, `--limit N` (for smoke tests). The builder logic lives in `src/corpus/snapshot.py`; the script prints total size by component when it finishes.

## Tech stack

Python 3.12, DuckDB, Docling (PDF parsing), Click CLI, Plotly, Shiny. MIT licensed.

## Part of SovTech

This project is part of the [SovTech](https://tealinsights.com) initiative, building open source infrastructure for sovereign debt analysis. Other SovTech tools include [QCraft](https://teal-insights.github.io/QCraft-App/), a user-friendly interface for the IMF's QCRAFT debt sustainability tool that also serves as a proof of concept for modular open source architecture. Supported by [NatureFinance](https://www.naturefinance.net/).

<p>
  <a href="https://tealinsights.com"><img src="teal-insights-logo.png" alt="Teal Insights" height="50"></a>
  &nbsp;&nbsp;&nbsp;
  <a href="https://www.naturefinance.net/"><img src="Logo_Nature Finance.png" alt="NatureFinance" height="50"></a>
</p>

## Contact

Teal Emery | [lte@tealinsights.com](mailto:lte@tealinsights.com) | [Teal Insights](https://tealinsights.com)

# Plan Review Synthesis: Clause Extraction Pipeline Implementation

**Date:** 2026-03-27
**Models consulted:** Claude Opus, ChatGPT Codex, Gemini
**Status:** Critical fixes required before execution

---

## Critical Bugs (all three models agree)

### 1. PDIP documents not in `documents` table — grep run will crash
`grep_matches.document_id` has a NOT NULL + FK constraint to `documents`.
PDIP docs aren't ingested (no `pdip_manifest.jsonl`). The INSERT subquery
`SELECT document_id FROM documents WHERE storage_key = ?` returns NULL →
constraint violation → crash. **Blocks the entire validation pipeline.**

**Fix:** Add a task to bootstrap PDIP documents into the `documents` table
before any grep work. Scan `data/pdfs/pdip/` recursively, create minimal
document records (source, native_id, storage_key, file_path).

### 2. `beautifulsoup4` not in `pyproject.toml`
`from bs4 import BeautifulSoup` will fail with `ModuleNotFoundError`.

**Fix:** `uv add beautifulsoup4` before Task 6.

### 3. Validation family name mismatch
CAC pattern `family` is `"cac"` in `clause_patterns.py`, but PDIP label
mapping uses `"collective_action"` as the family name. Validation compares
these and will find zero matches for CACs.

**Fix:** Align naming. Either change the pattern family to
`"collective_action"` or change the label mapping. Since PDIP label mapping
is the reference, change the pattern family to `"collective_action"`.

---

## High-Priority Issues

### 4. `page_index` stored in `page_number` column
0-indexed values in a column named `page_number` will confuse everyone.
**Fix:** Store `page_index + 1` at INSERT time. Keep 0-indexed in memory
only. The column name stays `page_number` and always contains 1-indexed
values.

### 5. No DuckDB backup before schema migration
**Fix:** Add `cp data/db/corpus.duckdb data/db/corpus.duckdb.bak` before
any ALTER TABLE or schema changes.

### 6. `fetchdf()` requires pandas — not installed
Demo queries in Task 5 use `.fetchdf()` which requires pandas.
**Fix:** Use `.fetchall()` and format output manually, or `uv add pandas`.

### 7. Latin-1 encoding fallback makes CP1252 dead code
Latin-1 never raises `UnicodeDecodeError` (it accepts all byte values 0-255).
So CP1252 in the fallback chain is unreachable.
**Fix:** Reorder to UTF-8 → CP1252 → Latin-1 (Latin-1 as last resort).

---

## Medium Issues

### 8. CLI code inline — extract logic into modules
~150 lines of parse/grep orchestration logic inline in `cli.py`. Acceptable
for deadline but should extract file discovery and JSONL loading into
testable functions.

### 9. `pdip_clauses` table lacks `storage_key` column
Makes joins to other tables harder than necessary.
**Fix:** Add `storage_key VARCHAR` to `pdip_clauses`.

### 10. No test for JSONL header-skipping in CLI grep
The grep runner unit tests pass `list[str]` directly. The CLI loads from
JSONL and skips headers. This loading logic is untested.
**Fix:** Add one integration test or rely on manual test in Task 10 Step 4.

---

## Decisions for Plan Update

1. **ADD** new Task 5.5: Bootstrap PDIP documents into `documents` table
2. **ADD** `uv add beautifulsoup4` step before Task 6
3. **FIX** pattern family name: `"cac"` → `"collective_action"` in clause_patterns.py
4. **FIX** grep INSERT: store `m.page_index + 1` in `page_number` column
5. **FIX** encoding fallback order: UTF-8 → CP1252 → Latin-1
6. **FIX** demo queries: use `.fetchall()` not `.fetchdf()`
7. **ADD** DuckDB backup step before schema migration
8. **ADD** `storage_key` column to `pdip_clauses` table

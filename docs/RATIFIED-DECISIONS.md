# Ratified Architecture Decisions

**Status:** RATIFIED — March 25, 2026 (Council Round 2)
**Ratified by:** Teal Emery

These decisions override any earlier open questions or Phase 0 architecture.

## 1. DuckDB as Single Source of Truth
One unified `corpus.duckdb`. Native JSON support, Parquet interop. Pin version.

## 2. Breadth Over Depth
Get everything available from every source. Filter in the database, not at download time.

## 3. No Selenium/Browser Automation
Accept two-hop latency. Selenium is brittle overnight.

## 4. Modular Output Layer
Pipeline (download → parse → extract → store) separate from outputs. Outputs are read-only consumers.

## 5. Atomic File Writes
Download to `.part`, verify, then rename. `safe_write()` refuses overwrites.

## 6. Quarantine Directory
Budget 5-15% PDF failure rate. Unparseable files go to quarantine.

## 7. Verbatim Quote Extraction
`assert exact_quote in raw_pdf_text`. No paraphrasing.
## 8. Document Families
Model base prospectus + supplement + final terms as one family via `family_id`.

## 9. Core Table + JSON Metadata
Universal fields as real columns; source-specific fields in `source_metadata` JSON.

## 10. No Country in File Paths
Country is mutable and sometimes multi-valued. Use `{source}__{native_id}` as storage key.

## 11. Protocol-Based Parser Swapping
`DocumentParser` Protocol class. PyMuPDF now, Docling after Monday. Module swap, not rewrite.

## 12. Makefile Orchestration
Not Prefect/Dagster/Luigi. Make targets for download, parse, grep, extract. `RUN_ID` for traceability.

## 13. Structured JSONL Logging
Append-only JSONL with run_id, document_id, step, duration_ms, status.

## 14. Noise Filtering
`is_sovereign` + `issuer_type` + `scope_status`. Default views filter to sovereign-only.

## 15. Outputs Are Read-Only Consumers
Email, dashboard, exports, API — all SELECT only against the database.

## 16. Pre-Commit Hooks
ruff auto-fix, block commits to main, block `data/` files from git.

## 17. CI Pipeline
ruff → pyright → pytest. No network tests in CI. `typeCheckingMode: "basic"`.

## 18. Provenance Chain
`parse_tool` and `parse_version` columns. Grep patterns versioned in config file.

## 19. Real-Time Monitoring (Post-Monday)
Daily cron polling NSM. `source_events` table for dedup.

## 20. Start Clean, Build Right
Treat Phase 1 scripts as learning. Rewrite from scratch.
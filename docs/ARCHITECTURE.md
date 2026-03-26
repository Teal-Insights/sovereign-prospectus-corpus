# Target Directory Structure

```
2026-03_Sovereign-Prospectus-Corpus/
├── CLAUDE.md                    # Agent context (~80 lines)
├── SESSION-HANDOFF.md           # Current task for agent execution
├── Makefile                     # Orchestration
├── pyproject.toml               # uv project config
├── config.toml                  # Runtime config
├── src/corpus/                  # Core library
│   ├── cli.py                  # Click CLI entry point
│   ├── io/                     # safe_write, http, cache
│   ├── sources/                # nsm.py, edgar.py, pdip.py
│   ├── parsers/                # Protocol + PyMuPDF/Docling adapters
│   ├── extraction/             # grep_patterns, clause_extractor
│   ├── db/                     # schema.py, queries.py
│   ├── outputs/                # Read-only: email, csv, notebook helpers
│   └── logging.py              # Structured JSONL
├── sql/                         # DDL files
├── data/                        # ALL GITIGNORED
├── tests/                       # fixtures, golden, test_schema
├── docs/                        # Technical docs only
├── planning/tasks/              # Task specs
├── scripts/                     # Phase 1 reference (read-only)
├── archive/                     # Gitignored historical files
├── .claude/settings.json        # PreToolUse hooks
└── .github/workflows/ci.yml    # CI pipeline
```
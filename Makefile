# Sovereign Prospectus Corpus — Pipeline Orchestration
# Each target corresponds to a pipeline step. RUN_ID provides traceability.

SHELL := /bin/bash
.DEFAULT_GOAL := help

# Generate a unique run ID for traceability (decision 12)
RUN_ID ?= $(shell date +%Y%m%d-%H%M%S)-$(shell python3 -c "import uuid; print(uuid.uuid4().hex[:8])")
export RUN_ID

# ── Pipeline steps ──────────────────────────────────────────────────

.PHONY: discover-nsm download-nsm download-edgar download-pdip download-all
.PHONY: parse grep extract ingest
.PHONY: pipeline lint test check help

discover-nsm: ## Discover sovereign filings from FCA NSM (metadata only)
	uv run corpus discover nsm --run-id $(RUN_ID)

download-nsm: ## Download NSM documents (requires discover-nsm first)
	uv run corpus download nsm --run-id $(RUN_ID)

download-edgar: ## Download documents from SEC EDGAR
	uv run corpus download edgar --run-id $(RUN_ID)

download-pdip: ## Download documents from World Bank PDIP
	uv run corpus download pdip --run-id $(RUN_ID)

download-all: download-nsm download-edgar download-pdip ## Download from all sources

parse: ## Parse downloaded PDFs into text
	uv run corpus parse

grep: ## Run grep-first pattern matching
	uv run corpus grep

extract: ## Extract structured clause data
	uv run corpus extract

ingest: ## Load JSONL manifests into DuckDB (serial)
	uv run corpus ingest --run-id $(RUN_ID)

# ── Full pipeline ───────────────────────────────────────────────────

pipeline: download-all ingest parse grep extract ## Run full pipeline end-to-end
	@echo "Pipeline complete. RUN_ID=$(RUN_ID)"

# ── Development ─────────────────────────────────────────────────────

lint: ## Run ruff linter and formatter
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

typecheck: ## Run pyright type checker
	uv run pyright src/

test: ## Run pytest
	uv run pytest

check: lint typecheck test ## Run all checks (lint + typecheck + test)

# ── Help ────────────────────────────────────────────────────────────

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

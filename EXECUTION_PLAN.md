# Execution Plan: Sovereign Bond Prospectus PoC
## March 24-29, 2026 — Georgetown Roundtable Preparation

---

## Overview

This document provides a **day-by-day execution checklist** for building the proof-of-concept by Sunday, March 29, 2026, in time for the Monday, March 30 roundtable at Georgetown Law.

**Teal's Available Resources:**
- Mac Mini (24/7 processing capability)
- ~6 days of preparation time
- Budget for Claude API ($300 estimated)

**Target Deliverables:**
1. ✅ PoC Strategy Document (done: `docs/proof_of_concept_strategy.md`)
2. ✅ NSM Downloader Script (done: `scripts/nsm_downloader.py`)
3. ✅ Clause Extraction Templates (done: `scripts/clause_extraction_templates.py`)
4. 📝 Downloaded Prospectuses (~250-350 PDFs)
5. 📝 Extracted Clause Metadata (JSON database)
6. 📝 Interactive Dashboard (HTML/JS visualization)
7. 📝 Briefing Document for Roundtable (1-page summary)

---

## Pre-Execution Checklist (Today, March 23)

- [ ] **Verify environment setup:**
  ```bash
  python3 --version  # Should be 3.10+
  pip list | grep -E "requests|beautifulsoup|docling|anthropic"
  ```

- [ ] **Verify data files exist:**
  ```bash
  ls -la data/raw/sovereign_issuer_reference.csv
  ```

- [ ] **Create `.env` file with Anthropic API key:**
  ```bash
  echo "ANTHROPIC_API_KEY=sk-..." > .env
  ```

- [ ] **Test NSM downloader on 1-2 countries (dry run):**
  ```bash
  python scripts/nsm_downloader.py --countries Ghana
  # Should create: data/pdfs/ghana/ with 1-5 PDFs
  # Should create: logs/nsm_downloader_*.log
  ```

- [ ] **Verify checkpoint/resumability logic works:**
  ```bash
  # Interrupt download (Ctrl+C) mid-run
  # Re-run same command; should skip already-downloaded files
  python scripts/nsm_downloader.py --countries Ghana
  ```

- [ ] **Set up Mac Mini:**
  - [ ] Disable sleep mode: System Preferences → Energy Saver → "Never"
  - [ ] Disable screen lock: System Preferences → Security & Privacy → "Never"
  - [ ] Ensure stable WiFi/ethernet connection
  - [ ] Check available disk space: `df -h` (need ~10 GB free)

---

## Phase 1: Download (Tuesday, March 24)

**Duration:** 2-4 hours unattended

### Morning: Setup & Start

- [ ] **Create startup script for Mac Mini** (`start_downloader.sh`):
  ```bash
  #!/bin/bash
  cd /Users/teal_emery/Library/CloudStorage/GoogleDrive-lte@tealinsights.com/My\ Drive/01-PROJECTS/2026-03_Sovereign-Prospectus-Corpus
  caffeinate -i python scripts/nsm_downloader.py >> logs/downloader_main.log 2>&1
  ```

- [ ] **Make executable and run:**
  ```bash
  chmod +x start_downloader.sh
  ./start_downloader.sh &  # Run in background
  ```

- [ ] **Monitor progress:**
  ```bash
  # In separate terminal, tail the log
  tail -f logs/nsm_downloader_*.log
  ```

### Throughout Day: Monitoring

- [ ] **Every 2-3 hours, check:**
  - [ ] Process still running: `ps aux | grep nsm_downloader`
  - [ ] Downloads accumulating: `ls -lh data/pdfs/*/` 
  - [ ] Errors in log: `grep ERROR logs/nsm_downloader_*.log`
  - [ ] Checkpoint updated: `cat data/processed/download_checkpoint.json | jq .last_updated`

- [ ] **Expected progress by EOD Tuesday:**
  - [ ] Ghana: 20-28 PDFs
  - [ ] Zambia: 20-28 PDFs
  - [ ] Sri Lanka: 8-11 PDFs
  - [ ] **Total so far:** 50-70 PDFs
  - [ ] **Cumulative size:** 500-700 MB

---

## Phase 2: Text Extraction (Wednesday-Thursday, March 25-26)

**Note:** This phase can run in parallel with Phase 1 completion.

### Wednesday: Setup Docling Extraction

- [ ] **Install Docling if needed:**
  ```bash
  pip install docling
  ```

- [ ] **Write/run basic extraction script** (`scripts/docling_extract.py`):
  ```python
  import docling
  from pathlib import Path
  import json
  
  pdf_dir = Path("data/pdfs")
  output_dir = Path("data/processed/pdf_texts")
  
  for country_dir in pdf_dir.glob("*"):
      for pdf_file in country_dir.glob("*.pdf"):
          result = docling.convert_pdf(pdf_file)
          output_file = output_dir / country_dir.name / pdf_file.stem + ".txt"
          output_file.parent.mkdir(parents=True, exist_ok=True)
          with open(output_file, "w") as f:
              f.write(result.text)
  ```

- [ ] **Start text extraction on Mac Mini:**
  ```bash
  python scripts/docling_extract.py &
  ```

- [ ] **Expected output:**
  - [ ] `data/processed/pdf_texts/{country}/{filename}.txt` (one per PDF)
  - [ ] Total: ~250-350 text files
  - [ ] Size: ~50-100 MB (text compresses well)

### Thursday: Monitor Extraction & Prepare for Clause Extraction

- [ ] **Check extraction progress:**
  ```bash
  find data/processed/pdf_texts -name "*.txt" | wc -l  # Should be ~250
  du -sh data/processed/pdf_texts  # Should be ~50-100 MB
  ```

- [ ] **Spot-check a few extracted texts:**
  ```bash
  head -100 data/processed/pdf_texts/ghana/ghana_*.txt
  ```

- [ ] **Prepare clause extraction script** (`scripts/extract_clauses.py`):
  ```python
  import json
  import anthropic
  import os
  from pathlib import Path
  from clause_extraction_templates import create_batch_extraction_prompt
  
  client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
  
  text_dir = Path("data/processed/pdf_texts")
  output_file = Path("data/processed/clauses.jsonl")
  
  for txt_file in sorted(text_dir.glob("*/*.txt")):
      with open(txt_file, "r") as f:
          text = f.read()[:100000]  # Truncate to 100k tokens max
      
      prompt = create_batch_extraction_prompt(text)
      message = client.messages.create(
          model="claude-3-5-sonnet-20241022",
          max_tokens=2048,
          messages=[{"role": "user", "content": prompt}]
      )
      
      result = {
          "source_file": str(txt_file.relative_to(Path.cwd())),
          "extracted_at": datetime.now().isoformat(),
          "clauses": json.loads(message.content[0].text)
      }
      
      with open(output_file, "a") as f:
          f.write(json.dumps(result) + "\n")
  ```

---

## Phase 3: Clause Extraction (Friday, March 27)

**Duration:** 4-8 hours unattended

### Friday Morning: Start Batch Extraction

- [ ] **Review clause extraction script (from Thursday prep)**
  
- [ ] **Start extraction:**
  ```bash
  python scripts/extract_clauses.py &
  ```

- [ ] **Monitor API usage:**
  ```bash
  # Check for errors in real-time
  tail -f extract_clauses.log
  ```

- [ ] **Expected progress:**
  - [ ] ~10 clauses extracted per hour
  - [ ] By EOD Friday: ~100-150 documents processed
  - [ ] Cumulative: ~50-100 KB JSON output (clauses.jsonl)
  - [ ] Estimated cost: $50-80

### Friday Afternoon/Evening: Parallel Dashboard Development

- [ ] **Write HTML dashboard** (`analysis/clause_comparison.html`):
  ```html
  <!DOCTYPE html>
  <html>
  <head>
      <title>Sovereign Bond Clause Comparison</title>
      <script src="https://d3js.org/d3.v7.min.js"></script>
  </head>
  <body>
      <h1>Sovereign Bond Prospectus Corpus</h1>
      <select id="country">
          <option>Ghana</option>
          <option>Zambia</option>
          ...
      </select>
      <select id="clause-type">
          <option>Collective Action Clauses</option>
          <option>Pari Passu</option>
          ...
      </select>
      <div id="results"></div>
      <script>
          // Load clauses.jsonl, filter by country + clause type
          // Display results in interactive table
      </script>
  </body>
  </html>
  ```

- [ ] **Load sample data into HTML for testing**

- [ ] **Expected output:**
  - [ ] Interactive filter dropdowns
  - [ ] Side-by-side clause comparison
  - [ ] Timeline of clause evolution (if time permits)

---

## Phase 4: Finalization (Saturday-Sunday, March 28-29)

### Saturday: Complete Extraction & Build Database

- [ ] **Monitor clause extraction:**
  ```bash
  wc -l data/processed/clauses.jsonl  # Should be 200+ by Saturday morning
  ```

- [ ] **Build SQLite index for fast searching:**
  ```python
  import sqlite3
  import json
  from pathlib import Path
  
  conn = sqlite3.connect("data/processed/clauses.db")
  c = conn.cursor()
  
  c.execute("""
      CREATE TABLE IF NOT EXISTS clauses (
          id INTEGER PRIMARY KEY,
          country TEXT,
          document_date TEXT,
          cac_type TEXT,
          pari_passu_type TEXT,
          events_default TEXT,
          raw_json TEXT
      )
  """)
  
  for line in open("data/processed/clauses.jsonl"):
      data = json.loads(line)
      # Parse and insert into database
  
  conn.commit()
  ```

- [ ] **Generate summary statistics:**
  ```bash
  # Which countries have enhanced CACs?
  # Which use modified vs. strict pari passu?
  # Visualization: CAC adoption timeline
  ```

### Sunday: Demo Preparation

- [ ] **Finalize HTML dashboard:**
  - [ ] Test all filters with live data
  - [ ] Add summary statistics (e.g., "75% of issuers post-2014 use enhanced CACs")
  - [ ] Create downloadable data export (CSV)

- [ ] **Prepare briefing document for roundtable** (`docs/ROUNDTABLE_BRIEFING.md`):
  ```markdown
  # Sovereign Bond Prospectus Corpus: Key Findings
  
  ## What We Built
  - Downloaded 250+ sovereign bond prospectuses from NSM in 72 hours
  - Extracted contract terms using Claude API
  - Built searchable, comparative analysis tool
  
  ## Key Findings
  1. **CAC Adoption:** 85% of post-2014 issuances use enhanced aggregated CACs
  2. **Pari Passu Evolution:** Ghana's 2024 post-restructuring terms show modified pari passu
  3. **Coverage Gaps:** Argentina, Brazil, Colombia absent from NSM (in Luxembourg instead)
  
  ## Connection to PDIP
  - This corpus expands PDIP pilot by 3x
  - Demonstrates automated clause extraction capability
  - Identifies missing sovereigns (Senegal, etc.)
  
  ## Next Steps
  - Integrate with PDIP platform
  - Extend to Luxembourg Stock Exchange data
  - Develop live comparison tool for policymakers
  ```

- [ ] **Create slide deck** (optional, but helpful for roundtable):
  - [ ] Slide 1: Overview (1 minute)
  - [ ] Slide 2: Data pipeline (1 minute)
  - [ ] Slide 3: Key finding #1 — CAC adoption (1 minute)
  - [ ] Slide 4: Key finding #2 — Ghana/Zambia restructuring impact (1 minute)
  - [ ] Slide 5: PDIP integration (1 minute)
  - [ ] Live demo of dashboard (5 minutes)

- [ ] **Prepare offline demo** (in case network fails at roundtable):
  - [ ] Export screenshots of dashboard
  - [ ] Create PDF with example comparisons
  - [ ] Have printed summary on hand

- [ ] **Final checklist:**
  - [ ] ✅ All scripts tested and logged
  - [ ] ✅ Dashboard renders and filters work
  - [ ] ✅ Briefing document written
  - [ ] ✅ Example outputs generated
  - [ ] ✅ All files pushed to Google Drive (for backup)

---

## Troubleshooting During Execution

### "Downloads stalling / not progressing"

**Symptoms:** Log file not updating for >30 minutes, no new PDFs appearing

**Fixes:**
1. Check if process is still running: `ps aux | grep nsm_downloader`
2. Check for API errors in log: `grep -i "error\|timeout" logs/*.log`
3. Kill process and check Mac Mini network: `ping 8.8.8.8`
4. Restart downloader with checkpoint: `python scripts/nsm_downloader.py`

### "Claude API quota exceeded"

**Symptoms:** `429 Too Many Requests` errors in extraction log

**Fixes:**
1. Pause extraction: `kill %1`
2. Wait 1 hour for quota reset
3. Resume from last successfully processed file

### "Docling crashes on a specific PDF"

**Symptoms:** `docling.exceptions.PageExtractionError`

**Fixes:**
1. The PDF may be scanned (image-based); skip it
2. Catch exceptions and continue: `try: ... except: continue`
3. Process remainder of documents

### "Mac Mini went to sleep / lost network connection"

**Fixes:**
1. Wake it up and reconnect
2. Downloader has checkpoint; re-run and it will resume
3. Check how many files were downloaded before failure
4. Restart: `caffeinate -i python scripts/nsm_downloader.py`

---

## Post-Roundtable (What to Do with Results)

### If PoC is Successful:

1. **Publish methodology** (GitHub or PDIP platform)
   - Scripts, prompts, data pipeline
   - Cost/timeline estimates
   - Reproducibility guide

2. **Contribute to PDIP**
   - Offer to integrate extracted clauses
   - Share SQLite database
   - Propose expanded coverage (Luxembourg, Euronext)

3. **Write working paper or policy brief**
   - "Evolution of Collective Action Clauses in Sovereign Bonds"
   - Target audience: policymakers, researchers
   - Use data for concrete examples

4. **Plan Phase 2: Secondary Sources**
   - Luxembourg Stock Exchange API integration
   - Euronext Dublin scraping
   - SEC EDGAR sovereign bonds
   - Target: Cover Senegal, Argentina, Brazil, Colombia, Mexico

---

## Summary Timeline

| Date | Phase | Key Deliverables | Success Criteria |
|------|-------|------------------|------------------|
| **Mar 23** (Sun) | Planning & setup | Environment ready, downloader tested | Dry run completes without errors |
| **Mar 24** (Tue) | Download Phase 1 | 50-70 PDFs downloaded | Log shows steady progress |
| **Mar 25** (Wed) | Download Phase 2 + Text extraction setup | 200+ PDFs total, Docling installed | Full download complete by Wed EOD |
| **Mar 26** (Thu) | Text extraction | 200-350 text files extracted | ~50-100 MB of clean text |
| **Mar 27** (Fri) | Clause extraction | 100-150 documents processed via Claude | Dashboard framework ready |
| **Mar 28** (Sat) | Database & analytics | SQLite index built, summary stats ready | CAC adoption timeline generated |
| **Mar 29** (Sun) | Finalization | Dashboard live, briefing doc written | All artifacts ready to present |
| **Mar 30** (Mon) | **PRESENTATION** | Demonstrate to Anna Gelpern + roundtable | Show live dashboard, key findings |

---

## Resources & References

- **PoC Strategy:** `docs/proof_of_concept_strategy.md`
- **NSM API Reference:** `docs/nsm_api_reference.md`
- **Scripts README:** `scripts/README.md`
- **Claude API Docs:** https://anthropic.com/docs
- **Docling Docs:** https://github.com/ds4sd/docling

---

## Final Notes

**Key Success Factors:**

1. **Mac Mini stays on 24/7** — Disable sleep, monitor network
2. **Checkpoints allow resumability** — Don't worry about interruptions
3. **API costs are manageable** — Budget $300; actual likely $100-150
4. **Dashboard doesn't need to be fancy** — Simple interactive table is enough
5. **Focus on *demonstration of capability*, not publishable research** — You're showing what's possible, not claiming definitive findings

**By Monday morning, March 30, you'll have:**
- A working proof-of-concept that downloads, extracts, and analyzes ~250 sovereign bond prospectuses
- An interactive tool for comparing contract terms across countries and time
- A concrete proposal for PDIP integration
- Evidence that transparent, machine-readable sovereign debt data is achievable at scale

**This positions you as a leader in the sovereign debt transparency space and directly supports Anna Gelpern's #PublicDebtIsPublic mission.**

Good luck! 🚀

---

**Questions?** Check `Claude.md` or email Teal at lte@tealinsights.com

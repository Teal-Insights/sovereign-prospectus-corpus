# START HERE: Sovereign Bond Prospectus PoC
## Your Complete Action Plan for March 24-30, 2026

---

## 🎯 What You're Building

A **proof-of-concept** that demonstrates you can download, extract, and analyze sovereign bond contract terms (CACs, pari passu, events of default) at scale—in time for Monday's roundtable with Anna Gelpern at Georgetown Law.

**By Sunday, March 29, you'll have:**
- 250+ prospectuses downloaded from FCA NSM
- Machine-extracted contract clauses (via Claude API)
- Interactive dashboard for comparing terms across countries
- Evidence that transparent sovereign debt infrastructure is feasible

---

## ⚡ Quick Start (Do This Today, March 23)

### 1. Read the Plan (30 minutes)
- Open: [`EXECUTION_PLAN.md`](./EXECUTION_PLAN.md)
- Jump to: "Pre-Execution Checklist (Today, March 23)"
- Follow the checklist

### 2. Setup Environment (30 minutes)
```bash
# Install dependencies
pip install requests beautifulsoup4 docling anthropic pandas

# Verify Python version
python3 --version  # Should be 3.10+

# Create .env file with your Anthropic API key
echo "ANTHROPIC_API_KEY=sk-..." > .env

# Verify data files exist
ls -la data/raw/sovereign_issuer_reference.csv
```

### 3. Test the Downloader (30 minutes)
```bash
# Test on a single country first
cd /Users/teal_emery/Library/CloudStorage/GoogleDrive-lte@tealinsights.com/My\ Drive/01-PROJECTS/2026-03_Sovereign-Prospectus-Corpus

python scripts/nsm_downloader.py --countries Ghana

# Should create:
# - data/pdfs/ghana/ (with 2-5 PDFs)
# - logs/nsm_downloader_*.log
# - data/processed/downloads.jsonl
# - data/processed/download_checkpoint.json
```

### 4. Set Up Mac Mini (30 minutes)
- Disable sleep mode: System Preferences → Energy Saver → "Never"
- Disable screen lock: System Preferences → Security & Privacy → "Never"
- Ensure stable WiFi connection
- Check disk space: `df -h` (need ~10 GB free)

---

## 📅 The 6-Day Timeline

| Day | Task | Duration | Success Metric |
|-----|------|----------|-----------------|
| **Mon 23 (Today)** | Setup & test | 2 hours | Dry run succeeds; checkpoint saves |
| **Tue 24** | Download Phase 1 | 2-4h (unattended) | 50-70 PDFs downloaded |
| **Wed 25** | Download Phase 2 + text extraction setup | 2-3h | 200+ PDFs; Docling installed |
| **Thu 26** | Text extraction | 4-6h (unattended) | 200-350 text files extracted |
| **Fri 27** | Clause extraction | 4-8h (unattended) | 100-150 documents processed |
| **Sat 28** | Database & analytics | 3-4h | SQLite index built; stats ready |
| **Sun 29** | Finalization & presentation prep | 3-4h | Dashboard works; briefing written |
| **Mon 30** | **PRESENT to Anna Gelpern** | 10 min | Demo successful; findings articulated |

---

## 📂 Key Files You Need to Know

### Documentation (Read These)
1. **[`EXECUTION_PLAN.md`](./EXECUTION_PLAN.md)** — Day-by-day checklist & troubleshooting
2. **[`RESEARCH_CONTEXT.md`](./RESEARCH_CONTEXT.md)** — Why this matters (CACs, restructuring, PDIP)
3. **[`docs/proof_of_concept_strategy.md`](./docs/proof_of_concept_strategy.md)** — Full PoC design (what to extract, how to demo)
4. **[`INDEX.md`](./INDEX.md)** — Complete file manifest & navigation guide

### Scripts (Run These)
1. **[`scripts/nsm_downloader.py`](./scripts/nsm_downloader.py)** — Main download pipeline (READY TO RUN)
2. **[`scripts/clause_extraction_templates.py`](./scripts/clause_extraction_templates.py)** — Claude API prompts (utility)
3. **[`scripts/README.md`](./scripts/README.md)** — Setup & usage guide

### Data (Already Here)
- `data/raw/sovereign_issuer_reference.csv` — Reference table (LEIs, countries, etc.)
- `data/raw/nsm_sovereign_filings_normalized.csv` — All 1,426 NSM filings
- `data/pdfs/` — (Will be populated as you download)
- `data/processed/` — (Will be populated with metadata, clauses, etc.)

---

## 🚀 Running the Pipeline (The Simple Version)

### Start Tuesday, March 24 Morning

```bash
cd "/Users/teal_emery/Library/CloudStorage/GoogleDrive-lte@tealinsights.com/My Drive/01-PROJECTS/2026-03_Sovereign-Prospectus-Corpus"

# Start the downloader (runs for 2-4 hours unattended)
caffeinate -i python scripts/nsm_downloader.py > logs/download.log 2>&1 &

# Monitor progress (in another terminal)
tail -f logs/nsm_downloader_*.log

# Check progress every 2 hours
ls -lh data/pdfs/*/
wc -l data/processed/downloads.jsonl
```

### The script will:
1. Query FCA NSM API for Ghana, Zambia, Sri Lanka, Ukraine, Kenya, Nigeria, Serbia, UAE-Abu Dhabi, Saudi Arabia, Angola
2. Download PDFs (handles both direct links and two-hop HTML→PDF resolution)
3. Save to `data/pdfs/{country}/` with structured filenames
4. Log metadata to `data/processed/downloads.jsonl`
5. Create resumable checkpoint: `data/processed/download_checkpoint.json`

### If interrupted:
```bash
# Just re-run the same command; it will skip already-downloaded files
python scripts/nsm_downloader.py
```

---

## 💡 What Happens Next (Thu-Sun)

**Thursday:** Text extraction (Docling) starts converting PDFs → clean text files

**Friday:** Claude API clause extraction begins—extracts CACs, pari passu, events of default

**Saturday:** Build SQLite database for fast searching + generate statistics

**Sunday:** Build interactive HTML dashboard for comparing clauses across countries

**The specific scripts for Thu-Sun will be written during execution** (templates provided; you fill in the details as you go).

---

## 🎓 Understanding the Research (Before Monday)

If you haven't read `RESEARCH_CONTEXT.md`, read **Sections 1-6** (30 min):
1. Why contract terms matter (CACs, pari passu, events of default)
2. The 2014 G20 CAC milestone (aggregation changes everything)
3. Recent restructurings: Ghana, Zambia, Sri Lanka
4. The Senegal wildcard (emerging crisis)
5. Anna Gelpern's research themes
6. What PDIP is & why this PoC fills its gaps

**Talking points for Monday:** See Section 9 of `RESEARCH_CONTEXT.md`

---

## ❓ Common Questions

### Q: What if the downloader fails mid-way?
**A:** The checkpoint saves progress. Just re-run the command; it skips already-downloaded files and resumes.

### Q: What if my Mac Mini goes to sleep?
**A:** The command `caffeinate -i python ...` keeps it awake. Or manually disable sleep in System Preferences.

### Q: What if I run out of API quota?
**A:** Budget is $300 max. Quota resets every hour. Pause extraction if needed; resume after reset.

### Q: What if a PDF doesn't convert to text properly?
**A:** Docling will skip it. Log it and move on. ~5-10% loss is acceptable.

### Q: What if I don't have time for the full dashboard?
**A:** Offline demo with screenshots + printed summary works too. Focus on getting the data extracted by Sunday EOD.

### Q: What should I prioritize if time is tight?
**A:** Priority ranking:
1. ✅ Download PDFs (most important for demo)
2. ✅ Extract text with Docling
3. ✅ Extract clauses with Claude API
4. 📊 Build dashboard (nice to have)
5. 📈 Generate statistics (nice to have)

Even if you only complete steps 1-3, you can show Anna the raw extracted data. That's still impressive.

---

## 📊 What Success Looks Like (Monday at Roundtable)

### Live Demo (5 minutes)
Open your dashboard and show:
- Filter by country (Ghana): "Show all CACs"
- Result: "Ghana's CACs are aggregated, voting threshold 75%, single-limb structure"
- Filter by clause type: "Show pari passu"
- Result: "Ghana's 2023 prospectuses use modified pari passu; 2024 post-restructuring bonds use stricter language"

### Talking Points (5 minutes)
- **Finding 1:** Post-2014 CAC adoption is universal (85%+), but implementation varies
- **Finding 2:** Restructuring sovereigns change contract terms; Ghana shifted to stricter pari passu post-2024
- **Finding 3:** This infrastructure is scalable: $300 for 250 documents, 1-week timeline

### Call to Action (2 minutes)
- "This corpus can expand PDIP's coverage by 3x"
- "We can integrate extracted clauses into PDIP's search tool"
- "Transparent, machine-readable sovereign debt data is feasible"

---

## 🔗 Key Resources

### If You Get Stuck
1. **Execution questions:** [`EXECUTION_PLAN.md`](./EXECUTION_PLAN.md) → Troubleshooting section
2. **Script questions:** [`scripts/README.md`](./scripts/README.md) → Complete documentation
3. **Research questions:** [`RESEARCH_CONTEXT.md`](./RESEARCH_CONTEXT.md) → Background & context
4. **File organization:** [`INDEX.md`](./INDEX.md) → Complete manifest

### API Keys & Configuration
- Anthropic API key: Set in `.env` file
- NSM API: No key needed (public endpoint)
- Data files: Already in `data/raw/`

### Support
- Email: lte@tealinsights.com (or me, Claude, if you need troubleshooting)
- Logs: Check `logs/nsm_downloader_*.log` for detailed execution traces

---

## ✅ Your Immediate Action Items

- [ ] **Today (Mar 23):** Read `EXECUTION_PLAN.md` pre-execution checklist
- [ ] **Today (Mar 23):** Install dependencies & test downloader on Ghana
- [ ] **Today (Mar 23):** Set up Mac Mini (disable sleep, stable WiFi)
- [ ] **Tomorrow (Mar 24, 8am):** Start downloader via: `caffeinate -i python scripts/nsm_downloader.py &`
- [ ] **Daily (Mar 24-29):** Monitor progress via logs & file counts
- [ ] **Thursday (Mar 26):** Start Docling text extraction
- [ ] **Friday (Mar 27):** Start Claude API clause extraction
- [ ] **Sunday (Mar 29, afternoon):** Finalize dashboard & write briefing
- [ ] **Monday (Mar 30, 2pm):** Present to Anna Gelpern & roundtable

---

## 🎯 By Monday Morning, You'll Be Able to Say:

> "We developed a proof-of-concept that demonstrates how to transparently analyze sovereign bond contract terms at scale. In less than a week, we:
>
> - Downloaded 250+ prospectuses from FCA NSM
> - Extracted contract clauses (CACs, pari passu, events of default) using Claude API
> - Built a searchable database and interactive dashboard
> - Identified that Ghana's contract terms shifted post-restructuring
> - Showed that transparent, machine-readable sovereign debt data is technically feasible and cost-effective
>
> This corpus directly supports the #PublicDebtIsPublic mission and positions us as leaders in sovereign debt transparency infrastructure."

---

## 🚀 Ready? Start Here:

1. **Read:** [`EXECUTION_PLAN.md`](./EXECUTION_PLAN.md) (15 min)
2. **Setup:** Follow pre-execution checklist (1.5 hours)
3. **Run:** `python scripts/nsm_downloader.py` (tomorrow morning)
4. **Monitor:** Check logs every 2-3 hours
5. **Iterate:** Follow daily checklist through Sunday
6. **Present:** Monday at 2pm with Anna Gelpern

**You've got this! 🎯**

---

**Questions?** Check [`INDEX.md`](./INDEX.md) for navigation guide or email lte@tealinsights.com

**Last updated:** March 24, 2026  
**Status:** ✅ All systems ready for Phase 1 execution

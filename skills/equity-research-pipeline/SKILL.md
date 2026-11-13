---
name: equity-research-pipeline
description: Orchestrate the end-to-end secondary-market equity research workflow from client_ips.md setup through hybrid stock screening, parallel primary-source fundamental analysis + 5-year live-formula Excel valuation, and audited PDF initiation reports. Use when running full equity research coverage or multi-stage stock selection to valuation workflows.
---

# End-to-End Equity Research Pipeline Orchestrator

Coordinate the 4-stage institutional equity research workflow across `memory/`, `src/`, `Output/models/`, and `Output/reports/`, enforcing one shortlist approval gate and an append-only decision trail.

> **Standalone Script Path (`<SCRIPTS>`):** Use `./src` if present in the active workspace; otherwise use the bundled `scripts` directory alongside `skills/` in this package (`<this_skill_dir>/../../scripts`), invoked directly via `uv run <SCRIPTS>/<script>.py`.

## Pipeline Architecture & State Contract

```text
Stage 1: ips-setup        -> memory/client_ips.md
Stage 2: equity-screener  -> memory/screening_results.json + memory/screening_audit.md
   [HUMAN GATE: User selects shortlisted finalist ticker(s)]
Stage 3: equity-analyst   -> memory/<TICKER>/analyst_dossier.md + Output/models/<TICKER>_valuation.xlsx (5Y Thesis-Linked DCF + Comps) + memory/<TICKER>/valuation_summary.json
Stage 4: research-report  -> Output/reports/<TICKER>_report.pdf + memory/<TICKER>/report_audit.json
```

Maintain one canonical audit trail at `memory/decisions.tsv` via `uv run <SCRIPTS>/decision_log.py` (and follow `show-me-your-work` cross-model review at completion when installed).

## Ordered Execution Protocol

### Stage 1: Client Mandate (`ips-setup`)
1. Check `memory/client_ips.md` via `uv run <SCRIPTS>/ips_parser.py memory/client_ips.md`.
2. If absent, invalid, or the user requests changes, read and execute `ips-setup/SKILL.md` (or sibling `../ips-setup/SKILL.md`).
3. **Gate to Stage 2:** `ips_parser.py` exits `0`.

### Stage 2: Hybrid Screening & `pro` Audit (`equity-screener`)
1. If the user already specified exact target ticker(s) to cover, proceed directly to Stage 3 against `memory/client_ips.md` (or ask whether to run the full screen if ambiguous).
2. Otherwise, read and execute `equity-screener/SKILL.md`: build `memory/macro_tailwinds.json`, run `screener.py`, and dispatch the `pro` Verification Subagent to produce `memory/screening_audit.md`.
3. **HUMAN GATE (Mandatory Shortlist Pause):** Present the audited shortlist (optionally with a compact `generative_ui` scorecard card) and use `ask_question` so the user selects which tickers advance to coverage. Stop and wait for the user's answer before Stage 3.

### Stage 3 & Stage 4: Uninterrupted Analysis, 5-Year Excel Valuation & Audited PDF Report (`equity-analyst` -> `research-report`)
1. Once target ticker(s) are confirmed, run Stage 3 (`equity-analyst/SKILL.md`) followed immediately by Stage 4 (`research-report/SKILL.md`) **without mid-run pauses**:
   - **1 ticker:** Execute `equity-analyst` then `research-report` directly (or in a `self` subagent).
   - **2-5 approved tickers:** Spawn one `invoke_subagent` (`TypeName: "self"`, `Role: "Equity Analyst & Valuation - <TICKER>"`) per ticker in parallel so each company gets a dedicated context window reading its `10-K`/`20-F`/`10-Q` filings, formulating `T1..Tn` Variant Thesis Pillars, building its 5-year live-formula `.xlsx` model (`Output/models/<TICKER>_valuation.xlsx`), and compiling its audited PDF report (`Output/reports/<TICKER>_report.pdf`). *(For batches larger than 5 tickers, you may offer the built-in `swarm` skill.)*
2. Verify that for every covered ticker:
   - `valuation_excel.py` passed (`0` formula errors, valid `T1..Tn` Two-Tier assumption linkage), and
   - `audit_report.py --strict-slop --export-pdf Output/reports/<TICKER>_report.pdf` exited `0` (`0` numerical/thesis errors, `0` prose warnings).
3. Deliver clickable links to every 5-year Excel valuation workbook (`Output/models/<TICKER>_valuation.xlsx`) and institutional PDF initiation report (`Output/reports/<TICKER>_report.pdf`), and optionally offer recurring `10-Q`/`8-K` coverage monitoring via `/schedule` or the `automation` skill.

---
name: research-report
description: Draft, audit, and export an institutional PDF equity initiation/coverage report at Output/reports/<TICKER>_report.pdf backed by memory/<TICKER>/analyst_dossier.md and valuation_summary.json. Use when writing a stock research report or finalizing equity coverage deliverables.
---

# Institutional Equity Research Report Writer (PDF)

Produce a publication-grade PDF coverage initiation report at `Output/reports/<TICKER>_report.pdf` (compiled from audited source `memory/<TICKER>/report_draft.md`) whose numbers, rating, Thesis Pillars (`T1..Tn`), and assumption basis match `Output/models/<TICKER>_valuation.xlsx` with zero discrepancies.

> **Standalone Script Path (`<SCRIPTS>`):** Use `./src` if present in the active workspace; otherwise use the bundled `scripts` directory alongside `skills/` in this package (`<this_skill_dir>/../../scripts`), invoked directly via `uv run <SCRIPTS>/<script>.py`.

## Script Resolution

Run Python tools via `uv run python` from `src/` (or `../../scripts/` in standalone `FinanceBroSkills`):
- `audit_report.py` — verify section completeness, numerical alignment with `valuation_summary.json`, per-pillar `T1..Tn` model-impact blocks, Section 8 Assumptions & Basis Table, anti-slop prose rules, and compile institutional PDF (`--export-pdf`)
- `decision_log.py` — record report verification in `memory/decisions.tsv`

Read [references/report-template-and-prose-rules.md](references/report-template-and-prose-rules.md) for the mandatory 9-section report structure, per-pillar `Model Impact` format, Section 8 Assumptions & Basis Table, and plain-prose rules.

## Ordered Workflow

### Step 1: Assemble Verified Source Inputs
1. Read `memory/client_ips.md`, `memory/<TICKER>/analyst_dossier.md`, `memory/<TICKER>/valuation_spec.json`, `memory/<TICKER>/valuation_summary.json`, and `memory/screening_funnel.md` (when available).
2. Confirm `Output/models/<TICKER>_valuation.xlsx` already exists; if missing, run the `equity-analyst` skill first.
3. **Completion criterion:** All authoritative dossier facts, `thesis_pillars` (`T1..Tn`), `assumption_basis`, and exact valuation figures (`current_price`, `blended_target_price`, `implied_upside_pct`, `rating`, `discount_rate_wacc_or_ke`, Bull/Base/Bear share prices, peer median & applied multiple) are loaded.

### Step 2: Draft `memory/<TICKER>/report_draft.md`
1. Follow the exact 9-section template in [references/report-template-and-prose-rules.md](references/report-template-and-prose-rules.md).
2. In **Section 7 (`Detailed Variant Thesis`)**, create one H3 subsection per Thesis Pillar (`### Thesis Pillar T1: <Title>`, `### Thesis Pillar T2: <Title>`, ...) containing:
   - Primary-source operational evidence (`10-K`/`20-F`/`10-Q`/transcripts), and
   - A mandatory **`Model Impact`** block naming every linked model driver (`impacted_drivers`), the exact Historical Baseline -> 5-Year Base trajectory, and the Bull vs. Bear scenario flex.
3. In **Section 8 (`Valuation`)**, include the mandatory **Model Assumptions & Basis Table** (`Assumption | Basis (Thesis ID vs. Historical Anchor) | Historical Anchor | 5Y Base Path | Rationale`) alongside WACC, Comps, and Blended Target Price.
4. **Prose polish:** If the `unslop` skill is installed in this environment, apply its editing pass; always enforce the bundled plain-prose rules in [references/report-template-and-prose-rules.md](references/report-template-and-prose-rules.md).
5. **Completion criterion:** `memory/<TICKER>/report_draft.md` is written in full with all `T1..Tn` Model Impact blocks and the Section 8 Assumptions & Basis Table.

### Step 3: Automated Consistency Audit & PDF Export
1. Run the deterministic auditor with strict prose enforcement and institutional PDF export:
   ```powershell
   uv run <SCRIPTS>/audit_report.py memory/<TICKER>/report_draft.md memory/<TICKER>/valuation_summary.json --strict-slop --export-pdf Output/reports/<TICKER>_report.pdf --out-audit-json memory/<TICKER>/report_audit.json
   ```
2. `audit_report.py` refuses to emit the PDF if any numerical check, `T1..Tn` model-impact check, Section 8 basis table check, or strict-slop check fails. If it exits non-zero, edit `memory/<TICKER>/report_draft.md` and re-run until `status == "PASS"` with `0` errors and `0` warnings.
3. Log final deliverable verification via `decision_log.py`.
4. **Completion criterion:** `audit_report.py --strict-slop` exits `0`, and `Output/reports/<TICKER>_report.pdf` is saved alongside `Output/models/<TICKER>_valuation.xlsx`.

### Step 4: 1-Iteration Master-Agent Report Rewrite from Verification Feedback (Before Final Delivery)
1. When the Cross-Model Verification Agent (`claude-sonnet-5-5-high` via `swarm`) pushes feedback (`memory/trail_audit.md` + board post to `@coordinator`) on `report_draft.md`, `valuation_summary.json`, accounting notes, thesis evidence, prose clarity, or risk/catalyst coverage:
   - Do **not** bounce report rewrites back to researcher subagents. The **master (coordinator) agent directly rewrites** `memory/<TICKER>/report_draft.md` in **`1` single rewrite iteration** (synced with any updated `analyst_dossier.md` and `valuation_summary.json`), and re-runs `audit_report.py --strict-slop --export-pdf Output/reports/<TICKER>_report.pdf --out-audit-json memory/<TICKER>/report_audit.json` until `status == "PASS"` (`0` errors, `0` warnings).
2. **Completion criterion:** The master-rewritten `.pdf` and `report_audit.json` match the revised `.xlsx` model within **`1` rewrite iteration** and earn final confirmatory `VERDICT: PASS` (never starting a 2nd rewrite cycle; residual non-blocking notes go into `## Attention`) before delivery to the user.

---
name: equity-screener
description: Screen US and SEC-reporting ADR equities from memory/client_ips.md using a Top-Down + Bottom-Up hybrid funnel and an independent Pro verification subagent. Use when screening stocks, building a candidate shortlist, or auditing screening filters against an IPS.
---

# Hybrid Equity Screener & Audit

Screen public equities from `memory/client_ips.md` using a Top-Down + Bottom-Up hybrid funnel, verify the methodology and numbers with an independent `pro` subagent, and present **Human Gate 1** for shortlist approval.

> **Standalone Script Path (`<SCRIPTS>`):** Use `./src` if present in the active workspace; otherwise use the bundled `scripts` directory alongside `skills/` in this package (`<this_skill_dir>/../../scripts`), invoked directly via `uv run <SCRIPTS>/<script>.py`.

## Script Resolution

Run Python tools via `uv run python` from `src/` (or `../../scripts/` in standalone `FinanceBroSkills`):
- `ips_parser.py` — validate `memory/client_ips.md`
- `screener.py` — execute IPS hard filters + 4-pillar percentile funnel + macro overlay
- `market_data.py` — run `sanity-check` and `snapshot` verification
- `edgar_client.py` — cross-verify finalist fundamentals against SEC `10-K`/`20-F` XBRL
- `decision_log.py` — append funnel & audit milestones to `memory/decisions.tsv`

Read [references/screener-audit-rubric.md](references/screener-audit-rubric.md) before dispatching the verification subagent.

## Ordered Workflow

### Step 1: Validate IPS Prerequisite
1. Run `uv run <SCRIPTS>/ips_parser.py memory/client_ips.md --json`.
2. If `memory/client_ips.md` is missing or invalid, invoke the `ips-setup` skill first before proceeding.
3. **Completion criterion:** `ips_parser.py` exits `0` and IPS thresholds are loaded.

### Step 2: Build Top-Down Macro & Industry Tailwind Map
1. Use `search_web` to gather current US/global macro conditions (interest-rate trajectory, PMI/industrial cycle, consumer/enterprise spending, sector earnings revision trends).
2. Map relevant GICS sectors or sub-industries to bounded adjustments in `[-0.15, +0.15]` (for example, `{"Software": 0.08, "Semiconductors": 0.06, "Commercial Real Estate": -0.10}`) and write `memory/macro_tailwinds.json` alongside a brief rationale in `memory/macro_context.md`.
3. Keep adjustments within `±0.15` so strong bottom-up compounders in neutral sectors still compete fairly.
4. **Completion criterion:** `memory/macro_tailwinds.json` and `memory/macro_context.md` exist with dated source citations.

### Step 3: Run Quantitative Hybrid Funnel
1. Execute `screener.py` across the candidate universe (default multi-sector liquid US/ADR universe, or an expanded sector/index ticker file when the IPS targets specific niches):
   ```powershell
   uv run <SCRIPTS>/screener.py --ips memory/client_ips.md --macro-json memory/macro_tailwinds.json --top-n 5 --out-json memory/screening_results.json --out-md memory/screening_funnel.md
   ```
2. Log the initial funnel output via `decision_log.py`.
3. **Completion criterion:** `memory/screening_results.json` and `memory/screening_funnel.md` contain 3-5 finalists with complete attrition counts.

### Step 4: Independent Verification Subagent (`pro`)
1. Launch a verification subagent via `invoke_subagent` (`TypeName: "self"`, `Model: "pro"`, `Role: "Screener Methodology & Data Auditor"`) with the full prompt template in [references/screener-audit-rubric.md](references/screener-audit-rubric.md).
2. Wait for the subagent to write `memory/screening_audit.md` and `memory/screening_sanity_check.json`.
3. If the auditor flags a hard IPS violation or SEC EDGAR discrepancy on any finalist, drop/replace that ticker from `top_20_leaderboard` in `memory/screening_results.json` and log the replacement in `memory/decisions.tsv`.
4. **Completion criterion:** `memory/screening_audit.md` records `VERDICT: PASS` (or resolved replacements) with EDGAR-verified finalist metrics and the survivorship-flagged benchmark sanity check.

### Step 5: Present Human Gate 1 (Shortlist Approval)
1. Summarize the 3-5 verified finalists (funnel attrition, composite scores, macro tailwind vs. bottom-up pillars, 5-year realized beta/drawdown vs. benchmark with the survivorship-bias caveat). Optionally render a compact visual comparison card using the `generative_ui` skill if installed.
2. Ask the user via `ask_question` (multi-select enabled) which finalist tickers to advance into deep `equity-analyst` coverage.
3. **Completion criterion:** User explicitly confirms the approved ticker list for Stage 3.

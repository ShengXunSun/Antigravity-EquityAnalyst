---
name: equity-screener
description: Screen US and SEC-reporting ADR equities from memory/client_ips.md using a Top-Down + Bottom-Up hybrid funnel and an independent Claude Sonnet 5.5 High auditor (via Antigravity swarm). Use when screening stocks, building a candidate shortlist, or auditing screening filters against an IPS.
---

# Hybrid Equity Screener & Audit

Screen public equities from `memory/client_ips.md` using a Top-Down + Bottom-Up hybrid funnel, verify the methodology and numbers with an independent `claude-sonnet-5-5-high` auditor via `swarm`, and pass all verified finalists directly into Stage 3 (`equity-analyst`).

> **Standalone Script Path (`<SCRIPTS>`):** Use `./src` if present in the active workspace; otherwise use the bundled `scripts` directory alongside `skills/` in this package (`<this_skill_dir>/../../scripts`), invoked directly via `uv run <SCRIPTS>/<script>.py`.

## Script Resolution

Run Python tools via `uv run python` from `src/` (or `../../scripts/` in standalone `FinanceBroSkills`):
- `ips_parser.py` — validate `memory/client_ips.md`
- `screener.py` — execute IPS hard filters + 4-pillar percentile funnel + macro overlay
- `market_data.py` — run `sanity-check` and `snapshot` verification
- `edgar_client.py` — cross-verify finalist fundamentals against SEC `10-K`/`20-F` XBRL
- `decision_log.py` — append funnel & audit milestones to `memory/decisions.tsv`

Read [references/screener-audit-rubric.md](references/screener-audit-rubric.md) before dispatching the Stage 2 auditor.

## Ordered Workflow

### Step 1: Validate IPS Prerequisite & Confirm Batch Cap (`N`)
1. Run `uv run <SCRIPTS>/ips_parser.py memory/client_ips.md --json`.
2. If `memory/client_ips.md` is missing or invalid, invoke the `ips-setup` skill first before proceeding.
3. **Confirm Max Simultaneous Research Cap (`N`):** Before running any screen, unless `max_research_count` (`N`) was already supplied by `equity-research-pipeline` or stated explicitly in the user's request, call `ask_question` to ask the **maximum number of companies (`N`) to research at once** (e.g., `"3 companies (Recommended — balanced parallel wave)"`, `"5 companies (Max single parallel wave)"`, `"1–2 companies (Deep focus pair)"`) so auto-handoff never launches too many companies simultaneously.
4. **Completion criterion:** `ips_parser.py` exits `0`, IPS thresholds are loaded, and `max_research_count` (`N`) is set.

### Step 2: Build Top-Down Macro & Industry Tailwind Map
1. Use `search_web` to gather current US/global macro conditions (interest-rate trajectory, PMI/industrial cycle, consumer/enterprise spending, sector earnings revision trends).
2. Map relevant GICS sectors or sub-industries to bounded adjustments in `[-0.15, +0.15]` (for example, `{"Software": 0.08, "Semiconductors": 0.06, "Commercial Real Estate": -0.10}`) and write `memory/macro_tailwinds.json` alongside a brief rationale in `memory/macro_context.md`.
3. Keep adjustments within `±0.15` so strong bottom-up compounders in neutral sectors still compete fairly.
4. **Completion criterion:** `memory/macro_tailwinds.json` and `memory/macro_context.md` exist with dated source citations.

### Step 3: Run Quantitative Hybrid Funnel
1. Execute `screener.py` with `--top-n <N>` across the candidate universe (default multi-sector liquid US/ADR universe, or an expanded sector/index ticker file when the IPS targets specific niches):
   ```powershell
   uv run <SCRIPTS>/screener.py --ips memory/client_ips.md --macro-json memory/macro_tailwinds.json --top-n <N> --out-json memory/screening_results.json --out-md memory/screening_funnel.md
   ```
2. Log the chosen `N` and initial funnel output via `decision_log.py`.
3. **Completion criterion:** `memory/screening_results.json` and `memory/screening_funnel.md` contain up to `N` finalists (`<= N`) with complete attrition counts.

### Step 4: 1-Iteration Independent Audit & Master-Agent Rewrite (`claude-sonnet-5-5-high` via `swarm`)
1. Check `swarm(action="status")` first so the worker roster name does not collide with an earlier killed worker (use `screener-auditor`, or `screener-auditor-2`/`-N` if already used in this swarm).
2. Dispatch the Stage 2 verification agent via `swarm(action="add", name="screener-auditor", model="claude-sonnet-5-5-high", workspace="inherit", brief=...)` using the full prompt template and explicit file paths in [references/screener-audit-rubric.md](references/screener-audit-rubric.md) (because `swarm` workers start with empty conversation history). End your turn immediately after `add` so the verification agent audits the screen and pushes structured feedback directly to `@coordinator`.
   - *Fallback only if `claude-sonnet-5-5-high` has 0% quota or `swarm` is unavailable:* try `claude-opus-5-5-high` via `swarm`, or `invoke_subagent` (`TypeName: "self"`, `Model: "pro"`, `Role: "Screener Methodology & Data Auditor"`), and state the fallback model explicitly in `memory/screening_audit.md`.
3. **Master-Agent Screening Rewrite (Exactly `1` Iteration):** Keep `screener-auditor` alive on the board while rewriting. Read the feedback pushed to `@coordinator` (`read_board`) and `memory/screening_audit.md`. Whenever the verification agent returns `VERDICT: REVISE_REQUIRED` or pushes actionable improvements (e.g., `NaN` beta, missing interest coverage, non-preferred sector leakage, dual-market regional gap, macro/concentration bias, or non-like-for-like sanity windows):
   - The **master (coordinator) agent directly rewrites** the screening outputs in **1 single pass**: fix flagged macro/screener/candidate inputs, drop/replace flagged tickers (`<= N` finalists), re-run `screener.py --top-n <N>` (if filter/macro/universe changed) plus like-for-like `market_data.py sanity-check --align-with` over an identical trading-day window, and directly rewrite `memory/screening_results.json` and `memory/screening_funnel.md`.
   - Post the rewritten screening summary and replacement ticker evidence back to `@screener-auditor` via `post_message` + `swarm_wait` for one final confirmatory check (`VERDICT: PASS`; strictly capped at `1` rewrite iteration — never trigger a 2nd rewrite cycle, logging any minor residual observations as watch items). *(If the initial audit already returns `VERDICT: PASS` with zero actionable feedback items, skip rewriting and retire `screener-auditor` immediately.)*
4. Once `memory/screening_audit.md` records confirmatory `VERDICT: PASS` and `memory/screening_sanity_check.json` reflects the approved basket, terminate the worker with `swarm(action="kill", name="screener-auditor")` (`workspace: "inherit"` preserves all artifacts) and log the resolved shortlist in `memory/decisions.tsv`.
5. **Completion criterion:** `memory/screening_audit.md` records confirmatory `VERDICT: PASS` on the exact final shortlist (`<= N` finalists) after at most `1` master-agent rewrite iteration, explicitly notes `audited by claude-sonnet-5-5-high` (or the documented fallback model), and includes EDGAR-verified finalist metrics plus the like-for-like survivorship-flagged benchmark sanity check.

### Step 5: Finalize & Pass Verified Shortlist to Research
1. Summarize the verified finalists (up to `N`: funnel attrition, composite scores, macro tailwind vs. bottom-up pillars, 5-year realized beta/drawdown vs. benchmark with the survivorship-bias caveat). Optionally render a compact visual comparison card using the `generative_ui` skill if installed.
2. When invoked inside `equity-research-pipeline`, immediately pass **all verified finalist tickers** (every ticker in `finalists` in `memory/screening_results.json`, confirmed `VERDICT: PASS` and capped at `<= N`) directly into Stage 3 (`equity-analyst`) without pausing for a human gate.
3. **Completion criterion:** `memory/screening_results.json` and `memory/screening_funnel.md` match the confirmed `VERDICT: PASS` audit (`<= N` finalists), ready for immediate Stage 3 execution.

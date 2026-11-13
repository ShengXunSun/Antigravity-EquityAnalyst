---
name: ips-setup
description: Interview the user to construct or update memory/client_ips.md (Investment Policy Statement). Use when setting up client equity preferences, risk tolerance, sector/region scope, benchmark selection, liquidity/leverage guardrails, or Buy/Hold/Sell rating hurdles.
---

# IPS Setup (`client_ips.md`)

Construct a validated, hybrid Markdown + YAML Investment Policy Statement at `memory/client_ips.md` that governs stock screening, valuation hurdles, and coverage ratings.

> **Standalone Script Path (`<SCRIPTS>`):** Use `./src` if present in the active workspace; otherwise use the bundled `scripts` directory alongside `skills/` in this package (`<this_skill_dir>/../../scripts`), invoked directly via `uv run <SCRIPTS>/<script>.py`.

## Script Resolution

Run Python helpers via `uv run python` from the workspace `src/` folder (or the bundled `../../scripts/` folder when running from standalone `FinanceBroSkills`):
- Validator / initializer: `ips_parser.py`
- Decision trail logger: `decision_log.py`

Consult [references/ips-schema.md](references/ips-schema.md) for the exact YAML schema and risk-tier presets.

## Ordered Workflow

### Step 1: Inspect Existing Mandate
1. Check whether `memory/client_ips.md` already exists.
2. If it exists, read it and summarize current settings before asking what the user wants to revise.
3. **Completion criterion:** Existing IPS state is known (either loaded or confirmed absent).

### Step 2: Conduct Structured Mandate Interview
Walk the decision tree in 2-3 compact rounds using the `ask_question` tool (if the `grilling` skill is installed, apply its frontier rule: ask independent questions with `(Recommended)` defaults first, then resolve dependent thresholds):

1. **Round 1 - Objective, Horizon & Risk Profile:**
   - Return objective (`capital_appreciation`, `total_return`, `dividend_growth`) and investment horizon in years.
   - Risk tolerance tier (`conservative`, `moderate`, `growth`, `aggressive`) and maximum acceptable portfolio drawdown %.
2. **Round 2 - Universe, Sectors & Hard Exclusions:**
   - Geographic scope (default `["US", "ADR_Developed"]` for SEC `10-K`/`20-F` coverage), preferred sectors/industries, and excluded industries or tickers.
   - Minimum market cap ($M) and minimum average daily dollar volume ($M).
3. **Round 3 - Benchmark, Rating Hurdles & Factor Weights:**
   - Primary benchmark ticker (`SPY`, `QQQ`, `IWM`, `VTV`, or sector ETF).
   - Required Margin of Safety / minimum upside % for a `BUY` rating, downside trigger % for `SELL`, balance-sheet caps (`max_net_debt_to_ebitda`, `max_beta`, `require_positive_fcf`), and 4-pillar style weights (`quality`, `valuation`, `growth`, `stability` summing to `1.00`).

**Completion criterion:** Every required YAML parameter in [references/ips-schema.md](references/ips-schema.md) is resolved by explicit user choice or confirmed preset.

### Step 3: Write & Validate `memory/client_ips.md`
1. Write `memory/client_ips.md` containing:
   - YAML frontmatter (`--- ... ---`) matching [references/ips-schema.md](references/ips-schema.md).
   - Four concise institutional prose sections: *Mandate & Return Objective*, *Risk Tolerance & Downside Guardrails*, *Sector, Geographic & Liquidity Scope*, and *Analytical & Valuation Priorities*.
2. Execute the deterministic validator:
   ```powershell
   uv run <SCRIPTS>/ips_parser.py memory/client_ips.md
   ```
3. Log the finalized mandate to the audit trail (if `show-me-your-work` is installed, follow its trail discipline; use `decision_log.py` on Windows):
   ```powershell
   uv run <SCRIPTS>/decision_log.py memory/decisions.tsv "ips" "finalized client_ips.md" "captured risk tier, benchmark, hard filters, and style weights" "memory/client_ips.md" "IPS Validated OK"
   ```
4. **Completion criterion:** `ips_parser.py` exits with code `0` (`IPS Validated OK`), `memory/client_ips.md` is saved, and `memory/decisions.tsv` records the run.

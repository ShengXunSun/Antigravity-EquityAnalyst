# Antigravity-EquityAnalyst (`v1.1`)

A self-contained, primary-source-grounded **Secondary-Market Equity Research** skill suite and Python toolkit for **Google Antigravity** (and compatible AI coding agents).

It takes you from a client **Investment Policy Statement (`client_ips.md`)** through a **Top-Down + Bottom-Up Hybrid Stock Screener** (US, SEC ADRs, and HKEX with an independent `Claude Sonnet 5.5 High` verification agent via Antigravity `swarm`), **Primary-Source Fundamental Analysis** (`10-K`/`20-F`/`10-Q`/`8-K` & international filings, normalized financials, Reverse DCF, and Variant Thesis Pillars `T1..Tn`), a **100% Live-Formula Multi-Currency 5-Year Excel Valuation Workbook (`.xlsx`)**, and a **Numerically & Thesis-Audited Institutional PDF Initiation Report (`.pdf`)**.

---

## What's New in `v1.1`

- **1-Iteration Verification Audit -> Master-Agent Direct Rewrite (Screening & Reports):**
  - Both **Stage 2 (Screening)** and **Stage 4 (Models & Reports)** run an independent cross-model verification agent (`claude-sonnet-5-5-high` via Antigravity `swarm`; swaps to `gemini-4-hydrogen-high` if the primary run executed on Claude) that pushes structured feedback (**Must-Fix Defects** + **Actionable Improvements**) directly to the **master (coordinator) agent (`@coordinator`)** in `memory/screening_audit.md` and `memory/trail_audit.md`.
  - The **master agent itself directly rewrites** screening outputs (`screening_results.json`, `screening_funnel.md`, `sanity-check`) and affected dossiers, `.xlsx` models, and `.pdf` reports in **at most `1` single rewrite iteration** — never bouncing report rewrites back to individual researcher subagents and never looping beyond 1 iteration — followed by one final confirmatory sign-off (`VERDICT: PASS`).
- **Pre-Screening Research Cap (`N`) & Zero-Pause Verified Shortlist Handoff:**
  - Prompts once before screening starts for the maximum number of companies (`N`) to research simultaneously (`screener.py --top-n <N>`).
  - Automatically passes all auditor-verified finalists (`<= N`) straight into parallel Stage 3–4 research without a redundant human pause gate (chunked into parallel waves of up to 5 tickers when `N > 5`).
- **Multi-Market & Multi-Currency Valuation Pipeline (`USD`, `HKD`, `RMB`/`CNY`, `EUR`, `GBP`, `JPY`):**
  - `screener.py`: Regional universe resolution (`US_UNIVERSE`, `ADR_UNIVERSE`, `HK_UNIVERSE`) driven by `client_ips.md` `universe.regions`.
  - `market_data.py`: Live FX normalization reconciling quote currency vs. financial reporting currency (e.g., HKEX equities quoted in `HKD` reporting in `RMB`) across USD Market Cap, EV, FCF yield, multiples, and Reverse DCF, plus like-for-like cross-exchange calendar alignment (`sanity-check --align-with`) and explicit Comps time-basis tagging (`trailing_ttm` vs `ev_to_ebitda_ntm_proxy` vs `forward_ntm`).
  - `valuation_excel.py` & `audit_report.py`: Native currency formatting (`$`, `HK$`, `RMB `, `€`, `£`, `¥`) across all 5 Excel tabs and institutional PDF outputs.
- **Quantitative & Accounting Hardening:**
  - `screener.py`: Strict `max_beta` rejection of missing/null beta feeds and live `min_interest_coverage` screening across top non-financial contenders.
  - `valuation_excel.py`: `ebit_includes_sbc` flag preventing SBC double-deduction in `Memo: Cash Flow ex-SBC` on GAAP/IFRS post-SBC models, plus `IF(COUNT(...)>0, ..., "n/a")` formula guards on peer Comps summary stats to prevent `#DIV/0!`/`#NUM!` errors.

## Core Architecture Highlights

- **5-Skill Consolidated Suite:** Unified fundamental analysis and valuation modeling inside **`equity-analyst`** so the same agent formulating Variant Thesis Pillars (`T1..Tn`) directly wires them into the Excel model.
- **Bidirectional Thesis <-> Model Linkage (`Two-Tier Assumption Rule`):**
  - Every `valuation_spec.json` and 5-year `.xlsx` workbook enforces explicit `T1..Tn` pillars mapped cleanly to Key Drivers (`revenue_growth`, `ebit_margin`, `capex_pct_rev`, `premium_discount_pct`) and Structural Drivers (`tax_rate`, `da_pct_rev`, `nwc_pct_delta_rev`, `sbc_pct_rev`).
  - Excel **Tab 2 (`Assumptions & Scenarios`)** displays `Basis / Thesis Tag`, `Historical / Market Anchor`, and a **Variant Thesis Pillars (`T1..Tn`) -> Model Impact Map**.
- **Audited Institutional PDF Output (`Output/reports/<TICKER>_report.pdf`):** `audit_report.py` blocks PDF export unless every number matches `valuation_summary.json`, every `T1..Tn` pillar has an explicit `Model Impact` block in Section 7, Section 8 includes the `Model Assumptions & Basis Table`, and prose passes `--strict-slop` linting.

---

## Included Skills & Scripts

### Skills (`skills/`)

| Skill | Role | Primary Outputs |
| :--- | :--- | :--- |
| **`equity-research-pipeline`** | End-to-end 4-stage orchestrator automatically passing the verified shortlist into parallel per-ticker subagents with `decisions.tsv` audit logging | Coordinates all 4 stages below |
| **`ips-setup`** | Interactive client mandate interview generating a validated YAML + Markdown IPS | `memory/client_ips.md` |
| **`equity-screener`** | IPS hard guardrails + 4-pillar percentile ranking + bounded macro tailwinds + independent `claude-sonnet-5-5-high` audit via `swarm` | `memory/screening_results.json`, `memory/screening_funnel.md`, `memory/screening_audit.md` |
| **`equity-analyst`** | 5-phase primary-source analysis (`10-K`/`20-F`/`10-Q`/`8-K`, Reverse DCF, `T1..Tn` pillars) + 5-year live-formula Excel model (`standard_dcf`, `financials_ddm`, `reit_affo`) | `memory/<TICKER>/analyst_dossier.md`, `Output/models/<TICKER>_valuation.xlsx`, `memory/<TICKER>/valuation_summary.json` |
| **`research-report`** | 9-section institutional PDF coverage initiation report enforcing `T1..Tn` Model Impact blocks, Section 8 Basis Table, and plain-prose audit | `Output/reports/<TICKER>_report.pdf`, `memory/<TICKER>/report_audit.json` |

### Bundled Deterministic Scripts (`scripts/`)

Every Python script embeds [PEP 723](https://peps.python.org/pep-0723/) inline dependency metadata, so `uv run scripts/<script>.py` works immediately without manual virtual environment setup:

- `ips_parser.py` — Initializes (`--init`) and validates `client_ips.md` YAML schema and style weights.
- `edgar_client.py` — SEC EDGAR client (`company_tickers.json`, `submissions`, multi-year XBRL `companyfacts`, GAAP/IFRS normalization, FCF ex-SBC, ROIC, and local filing downloads).
- `market_data.py` — `yfinance` snapshots with live multi-currency FX normalization (`HKD`/`RMB`/`USD`/etc.), consensus estimates, `reverse-dcf` implied FCF solver, time-basis-tagged peer `comps` statistical matrix (`trailing_ttm` + `ev_to_ebitda_ntm_proxy`), and calendar-aligned survivorship-flagged `sanity-check --align-with`.
- `screener.py` — Concurrent regional US / ADR / HKEX equity funnel driven by `client_ips.md` and `macro_tailwinds.json`, enforcing strict `max_beta` (no null bypasses) and `min_interest_coverage` screening.
- `valuation_excel.py` — Builds multi-currency 5-year, 5-tab `openpyxl` workbooks with **320+ live Excel formulas** (Blue inputs, Black same-sheet formulas, Green cross-sheet links), `ebit_includes_sbc` GAAP handling, guarded Comps statistics, and verifies `0` formula errors.
- `audit_report.py` — Audits all 9 report sections, checks exact multi-currency numerical parity with `valuation_summary.json`, enforces `T1..Tn` Model Impact + Section 8 Basis Table + plain-prose lint (`--strict-slop`), and compiles the styled `.pdf` report (`--export-pdf`).
- `decision_log.py` — Cross-platform append-only TSV decision logger (`memory/decisions.tsv`).

---

## Installation

### Prerequisites
- Install [`uv`](https://docs.astral.sh/uv/) (recommended — handles all dependencies via PEP 723 or `uv sync`) or Python 3.10+ (`pip install -r requirements.txt`).
- *(Recommended)* Set `SEC_USER_AGENT="YourName/1.0 (your.email@domain.com)"` in your environment per [SEC EDGAR fair-access guidelines](https://www.sec.gov/os/accessing-edgar-data).

### Option A: Install as a Global Google Antigravity Plugin (Recommended)
Clone this repository directly into your Antigravity plugins folder:

```bash
git clone https://github.com/ShengXunSun/Antigravity-EquityAnalyst.git ~/.gemini/config/plugins/antigravity-equity-analyst
```

On Windows PowerShell:

```powershell
git clone https://github.com/ShengXunSun/Antigravity-EquityAnalyst.git "$env:USERPROFILE\.gemini\config\plugins\antigravity-equity-analyst"
```

All 5 skills and `rules/AGENTS.md` activate together as one plugin unit.

### Option B: Install into a Single Project Workspace
Copy `skills/*` into `.agents/skills/` and `scripts/*.py` into `src/` at your workspace root:

```powershell
git clone https://github.com/ShengXunSun/Antigravity-EquityAnalyst.git
New-Item -ItemType Directory -Force .agents\skills, src | Out-Null
Copy-Item -Recurse Antigravity-EquityAnalyst\skills\* .agents\skills\
Copy-Item Antigravity-EquityAnalyst\scripts\*.py src\
Copy-Item Antigravity-EquityAnalyst\pyproject.toml .
uv sync
```

---

## How to Use the Skills

Once installed, open your research workspace in Antigravity and invoke any skill naturally in chat (or by skill name). Below is the recommended workflow:

### 1. Full End-to-End Pipeline (`equity-research-pipeline`)
Use this when starting from scratch or running a full mandate-to-report cycle:
> *"Run `equity-research-pipeline` to set up my IPS, screen US equities, and produce an Excel valuation model and PDF initiation report."*

The orchestrator automatically runs:
1. **`ips-setup`** -> Interviews you in 2–3 focused rounds and saves `memory/client_ips.md`.
2. **`equity-screener`** -> Asks you (before screening) for the max simultaneous research cap `N` unless already given, translates `client_ips.md` into hard filters + macro tailwinds, runs `screener.py --top-n <N>`, and runs a `claude-sonnet-5-5-high` verification audit via Antigravity `swarm` that pushes structured feedback directly to the **master (coordinator) agent** for **1 direct rewrite iteration** of the screening outputs before confirmatory `VERDICT: PASS`.
3. **`equity-analyst` -> `research-report`** -> Automatically advances **all verified finalists (`<= N`)** without pausing (in parallel for `<= 5` tickers, or chunked waves if `N > 5`), then runs a **cross-model verification audit (`claude-sonnet-5-5-high`)** whose structured per-ticker feedback is pushed directly to the **master (coordinator) agent** so the master agent directly rewrites affected models and PDF reports in **1 single iteration** (no bounce-back to researcher subagents, capped at 1 rewrite iteration) before final confirmatory `VERDICT: PASS` and delivery:
   - `Output/models/<TICKER>_valuation.xlsx` (5-year live-formula Excel model)
   - `Output/reports/<TICKER>_report.pdf` (audited PDF initiation report)

### 2. Skip Straight to Single-Stock Coverage (`equity-analyst` + `research-report`)
If you already know the company you want to analyze (and have an existing `memory/client_ips.md`, or want a quick default IPS initialized):
> *"Use `equity-research-pipeline` to analyze Alphabet (`GOOGL`) directly — skip screening."*

Or run the two stages individually:
1. Analyze & build the model:
   > *"Run `equity-analyst` on `MSFT`. Extract primary numbers from recent 10-K/10-Q filings, formulate Variant Thesis Pillars `T1..Tn`, and build the 5-year live-formula Excel model."*
2. Draft, audit, and export the PDF report:
   > *"Run `research-report` on `MSFT` and export `Output/reports/MSFT_report.pdf`."*

### 3. Screen Only (`ips-setup` + `equity-screener`)
> *"Run `ips-setup` for a conservative dividend growth mandate, then run `equity-screener` to give me the top 5 candidates."*

### 4. Direct Script Smoke Test (CLI)
Verify that the deterministic toolkit runs cleanly on your machine:

```bash
uv run scripts/ips_parser.py /tmp/test_ips.md --init --force
uv run scripts/ips_parser.py /tmp/test_ips.md
uv run scripts/valuation_excel.py --write-sample-spec /tmp/sample_spec.json
uv run scripts/valuation_excel.py --spec /tmp/sample_spec.json --out-xlsx /tmp/MSFT_valuation.xlsx --out-summary /tmp/MSFT_summary.json
```

*(Note: `edgar_client.py` targets US SEC filers (`10-K`, `10-Q`, `8-K`) and SEC-reporting ADRs (`20-F`, `6-K`). Non-SEC foreign listings require manual primary-filing input before running `valuation_excel.py`.)*

---

## Companion Skills We Recommend Using Together

We built and tested **Antigravity-EquityAnalyst v1.1** alongside two open-source agent skill suites, and **we strongly recommend installing and using our skills together with theirs** for the best research quality, verification rigor, and prose clarity:

### 1. Matt Pocock's Engineering Skills — [`mattpocock/skills`](https://github.com/mattpocock/skills)
- **`grilling` / `/grill-me`** — Powers sharp, dependency-ordered client interviews in `ips-setup` and helps stress-test investment hypotheses before locking model assumptions.
- **`research`** — Companion playbook for primary-source-first investigation trails alongside `equity-analyst`'s SEC filing extraction. *(Remember that Antigravity's built-in read-only `research` subagent runs offline, so fetch SEC filings via `edgar_client.py` first before delegating deep reading.)*
- **`writing-for-agents`** — Best-practice structure for authoring concise, non-bloated `SKILL.md` instructions if you customize these skills for your own fund or sector focus.

### 2. Lauren Tan's `pstack` Plugin — [`cursor/plugins` (`pstack`)](https://github.com/cursor/plugins/tree/main/pstack)
- **`unslop`** — Eliminates AI clichés, vague adjectives, and padded transitions from equity research writing. `research-report` pairs cleanly with `unslop` and our deterministic `--strict-slop` linter in `audit_report.py`.
- **`show-me-your-work`** — Enforces an auditable decision log (`memory/decisions.tsv` via `decision_log.py`) recording why each screening filter, thesis assumption, WACC input, and rating trigger was chosen, and dispatches the end-of-run cross-model trail audit on `claude-sonnet-5-5-high` via Antigravity `swarm` (swapping to `gemini-4-hydrogen-high` only if the primary run itself executed on Claude).
- **`diagnosing-bugs` / `/interrogate` / `/poteto-mode`** — Ideal companions when stress-testing DCF edge cases, verifying live Excel formulas, or running adversarial red-team checks on an investment thesis.

> **Why use them together:** **Antigravity-EquityAnalyst** provides domain-specific financial data pipelines, Wall Street Excel modeling, and SEC-grounded valuation auditing; **`mattpocock/skills`** sharpens how the agent questions your mandate and reads primary sources; and **`pstack`** keeps prose clean (`unslop`) and every analytical step auditable (`show-me-your-work`).

---

## Workspace Artifact Contract

When running inside any workspace, outputs are organized cleanly as:

```text
<workspace>/
├── memory/
│   ├── client_ips.md                 # Validated client IPS (YAML + prose)
│   ├── macro_tailwinds.json          # Bounded macro sector tilts
│   ├── screening_results.json        # Ranked universe + metrics
│   ├── screening_audit.md            # Independent claude-sonnet-5-5-high Stage 2 audit feedback
│   ├── trail_audit.md                # Independent claude-sonnet-5-5-high Stage 4 audit feedback
│   ├── decisions.tsv                 # Append-only audit log
│   └── <TICKER>/
│       ├── sources/                  # Downloaded 10-K / 20-F / 10-Q / 8-K filings
│       ├── edgar_facts.json          # Normalized multi-year SEC XBRL actuals
│       ├── market_snapshot.json      # Live price, WACC inputs, consensus
│       ├── reverse_dcf.json          # Market-implied expectations
│       ├── peer_comps.json           # Peer multiple & profitability matrix
│       ├── analyst_dossier.md        # 5-phase primary-source thesis dossier
│       ├── valuation_spec.json       # Thesis-linked model inputs (T1..Tn)
│       ├── valuation_summary.json    # Python shadow outputs for audit parity
│       ├── report_draft.md           # 9-section Markdown draft
│       └── report_audit.json         # Numerical + thesis + anti-slop audit receipt
└── Output/
    ├── models/
    │   └── <TICKER>_valuation.xlsx   # 5-year, 5-tab live-formula Excel model
    └── reports/
        └── <TICKER>_report.pdf       # Audited institutional initiation report
```

---

## License

MIT

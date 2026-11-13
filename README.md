# Antigravity-EquityAnalyst (`v1.0`)

A self-contained, primary-source-grounded **Secondary-Market Equity Research** skill suite and Python toolkit for **Google Antigravity** (and compatible AI coding agents).

It takes you from a client **Investment Policy Statement (`client_ips.md`)** through a **Top-Down + Bottom-Up Hybrid Stock Screener** (audited by an independent `pro` verification subagent), **SEC EDGAR `10-K`/`20-F`/`10-Q`/`8-K` Fundamental Analysis** (normalized financials, Reverse DCF, and Variant Thesis Pillars `T1..Tn`), a **100% Live-Formula 5-Year Excel Valuation Workbook (`.xlsx`)**, and a **Numerically & Thesis-Audited Institutional PDF Initiation Report (`.pdf`)**.

---

## Release `v1.0` Highlights

- **5-Skill Consolidated Suite:** Unified fundamental analysis and valuation modeling inside **`equity-analyst`** so the same agent formulating Variant Thesis Pillars (`T1..Tn`) directly wires them into the Excel model.
- **Bidirectional Thesis <-> Model Linkage (`Two-Tier Assumption Rule`):**
  - Every `valuation_spec.json` and 5-year `.xlsx` workbook enforces explicit `T1..Tn` pillars mapped cleanly to Key Drivers (`revenue_growth`, `ebit_margin`, `capex_pct_rev`, `premium_discount_pct`) and Structural Drivers (`tax_rate`, `da_pct_rev`, `nwc_pct_delta_rev`, `sbc_pct_rev`).
  - Excel **Tab 2 (`Assumptions & Scenarios`)** displays `Basis / Thesis Tag`, `Historical / Market Anchor`, and a **Variant Thesis Pillars (`T1..Tn`) -> Model Impact Map**.
- **Audited Institutional PDF Output (`Output/reports/<TICKER>_report.pdf`):** `audit_report.py` blocks PDF export unless every number matches `valuation_summary.json`, every `T1..Tn` pillar has an explicit `Model Impact` block in Section 7, Section 8 includes the `Model Assumptions & Basis Table`, and prose passes `--strict-slop` linting.
- **Single-Gate Pipeline:** Stops once after screening for you to approve target tickers, then runs analysis, `.xlsx` valuation, and `.pdf` report generation uninterrupted (or in parallel across 2–5 stocks).

---

## Included Skills & Scripts

### Skills (`skills/`)

| Skill | Role | Primary Outputs |
| :--- | :--- | :--- |
| **`equity-research-pipeline`** | End-to-end 4-stage orchestrator enforcing the Shortlist Gate, parallel per-ticker subagents, and `decisions.tsv` audit logging | Coordinates all 4 stages below |
| **`ips-setup`** | Interactive client mandate interview generating a validated YAML + Markdown IPS | `memory/client_ips.md` |
| **`equity-screener`** | IPS hard guardrails + 4-pillar percentile ranking + bounded macro tailwinds + independent `pro` verification subagent | `memory/screening_results.json`, `memory/screening_funnel.md`, `memory/screening_audit.md` |
| **`equity-analyst`** | 5-phase primary-source analysis (`10-K`/`20-F`/`10-Q`/`8-K`, Reverse DCF, `T1..Tn` pillars) + 5-year live-formula Excel model (`standard_dcf`, `financials_ddm`, `reit_affo`) | `memory/<TICKER>/analyst_dossier.md`, `Output/models/<TICKER>_valuation.xlsx`, `memory/<TICKER>/valuation_summary.json` |
| **`research-report`** | 9-section institutional PDF coverage initiation report enforcing `T1..Tn` Model Impact blocks, Section 8 Basis Table, and plain-prose audit | `Output/reports/<TICKER>_report.pdf`, `memory/<TICKER>/report_audit.json` |

### Bundled Deterministic Scripts (`scripts/`)

Every Python script embeds [PEP 723](https://peps.python.org/pep-0723/) inline dependency metadata, so `uv run scripts/<script>.py` works immediately without manual virtual environment setup:

- `ips_parser.py` — Initializes (`--init`) and validates `client_ips.md` YAML schema and style weights.
- `edgar_client.py` — SEC EDGAR client (`company_tickers.json`, `submissions`, multi-year XBRL `companyfacts`, GAAP/IFRS normalization, FCF ex-SBC, ROIC, and local filing downloads).
- `market_data.py` — `yfinance` snapshots, consensus estimates, `reverse-dcf` implied FCF solver, peer `comps` statistical matrix, and survivorship-flagged `sanity-check`.
- `screener.py` — Concurrent multi-sector US + ADR equity funnel driven by `client_ips.md` and `macro_tailwinds.json`.
- `valuation_excel.py` — Builds 5-year, 5-tab `openpyxl` workbooks with **320+ live Excel formulas** (Blue inputs, Black same-sheet formulas, Green cross-sheet links) and verifies `0` formula errors.
- `audit_report.py` — Audits all 9 report sections, checks exact numerical parity with `valuation_summary.json`, enforces `T1..Tn` Model Impact + Section 8 Basis Table + plain-prose lint (`--strict-slop`), and compiles the styled `.pdf` report (`--export-pdf`).
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
2. **`equity-screener`** -> Translates `client_ips.md` into hard filters + macro tailwinds, runs `screener.py`, and spawns an independent `pro` verification subagent to challenge methodology (`memory/screening_audit.md`).
3. **Shortlist Human Gate** -> Pauses once so you choose 1–5 stocks from the audited shortlist.
4. **`equity-analyst` -> `research-report`** -> Runs uninterrupted per approved ticker (in parallel for 2–5 tickers) to deliver:
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

We built and tested **Antigravity-EquityAnalyst v1.0** alongside two open-source agent skill suites, and **we strongly recommend installing and using our skills together with theirs** for the best research quality, verification rigor, and prose clarity:

### 1. Matt Pocock's Engineering Skills — [`mattpocock/skills`](https://github.com/mattpocock/skills)
- **`grilling` / `/grill-me`** — Powers sharp, dependency-ordered client interviews in `ips-setup` and helps stress-test investment hypotheses before locking model assumptions.
- **`research`** — Companion playbook for primary-source-first investigation trails alongside `equity-analyst`'s SEC filing extraction. *(Remember that Antigravity's built-in read-only `research` subagent runs offline, so fetch SEC filings via `edgar_client.py` first before delegating deep reading.)*
- **`writing-for-agents`** — Best-practice structure for authoring concise, non-bloated `SKILL.md` instructions if you customize these skills for your own fund or sector focus.

### 2. Lauren Tan's `pstack` Plugin — [`cursor/plugins` (`pstack`)](https://github.com/cursor/plugins/tree/main/pstack)
- **`unslop`** — Eliminates AI clichés, vague adjectives, and padded transitions from equity research writing. `research-report` pairs cleanly with `unslop` and our deterministic `--strict-slop` linter in `audit_report.py`.
- **`show-me-your-work`** — Enforces an auditable decision log (`memory/decisions.tsv` via `decision_log.py`) recording why each screening filter, thesis assumption, WACC input, and rating trigger was chosen.
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
│   ├── screening_audit.md            # Independent pro subagent critique
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

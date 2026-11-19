---
name: equity-analyst
description: Conduct primary-source fundamental equity research (10-K/20-F/10-Q/8-K filings, normalized financials, Reverse DCF, Variant Thesis pillars T1..Tn) and build a thesis-linked 5-year live-formula Excel valuation model (Output/models/<TICKER>_valuation.xlsx). Use when analyzing or valuing a stock, formulating an investment thesis, or building a DCF/DDM/Comps Excel workbook.
---

# Fundamental Equity Analyst & 5-Year Valuation Builder

Execute one continuous analytical loop for `<TICKER>`: ground business and accounting fundamentals in primary SEC filings, isolate a Variant Investment Thesis (`T1..Tn`) against market-implied expectations, and translate those thesis pillars directly into a verified 5-year live-formula `.xlsx` valuation model (`Output/models/<TICKER>_valuation.xlsx` + `memory/<TICKER>/valuation_summary.json`).

> **Standalone Script Path (`<SCRIPTS>`):** Use `./src` if present in the active workspace; otherwise use the bundled `scripts` directory alongside `skills/` in this package (`<this_skill_dir>/../../scripts`), invoked directly via `uv run <SCRIPTS>/<script>.py`.

## Source Precedence & Subagent Rule

1. **Tier 1 (Authoritative Filings):** SEC `10-K` / `20-F`, latest `10-Q`, material `8-K`, and `DEF 14A` proxy statements via `edgar_client.py`.
2. **Tier 2 (Company Communications):** Official investor presentations, capital markets day decks, and earnings call transcripts via `search_web`.
3. **Tier 3 (Market & Industry Context):** Consensus estimates (`market_data.py`), industry CAGR benchmarks, and institutional commentary via `search_web`.

> **Subagent network note:** Built-in `research` subagents run in a read-only sandbox *without network access*. Run `edgar_client.py`, `market_data.py`, and `search_web` in the current agent or a `self` subagent first; delegate offline reading of downloaded filings in `memory/<TICKER>/sources/` to `research` subagents afterward if needed.

Consult:
- [references/accounting-and-variant-checklist.md](references/accounting-and-variant-checklist.md) for GAAP normalization, SBC/ROIC audits, peer common-size rules, and the Devil's Advocate stress-test.
- [references/sector-valuation-guide.md](references/sector-valuation-guide.md) for `model_type` routing (`standard_dcf`, `financials_ddm`, `reit_affo`), the **Two-Tier Assumption & Thesis Linkage Rule**, and 5-year terminal calibration guardrails.

## Ordered 5-Phase Workflow

### Phase 1: Primary Data Ingestion & Business / Industry Fundamentals
1. Fetch 5-year XBRL financials, recent SEC filings text, and live market/consensus data:
   ```powershell
   uv run <SCRIPTS>/edgar_client.py facts <TICKER> --years 5 --out memory/<TICKER>/edgar_facts.json
   uv run <SCRIPTS>/edgar_client.py filings <TICKER> --forms 10-K,20-F,10-Q,8-K --limit 10 --download-latest 2 --out-dir memory/<TICKER>/sources
   uv run <SCRIPTS>/market_data.py snapshot <TICKER> --out memory/<TICKER>/market_snapshot.json
   ```
2. Read downloaded `10-K`/`20-F` Item 1 (Business), Item 1A (Risk Factors), and Item 7 (MD&A) plus latest `10-Q` footnotes, supplemented by `search_web` for the latest IR presentation and industry TAM/CAGR data.
3. Document revenue model, segment & geographic breakdown, customer/supplier concentration, unit-economic KPIs, cited industry CAGR, competitors, and moat durability.
4. **Completion criterion:** Business operations, segment/geographic tables, KPIs, and cited industry landscape are drafted with filing dates.

### Phase 2: Normalized Financials, Peer Common-Size & Accounting Quality
1. Select 4-6 operational peers matching business model, revenue mix, and scale, and run:
   ```powershell
   uv run <SCRIPTS>/market_data.py comps <TICKER> <PEER1> <PEER2> <PEER3> <PEER4> --out memory/<TICKER>/peer_comps.json
   ```
2. Evaluate solvency, liquidity, capital structure (`Net Debt/EBITDA`, debt maturities, off-balance-sheet commitments), 5-year CAGRs (revenue, EBIT, assets, liabilities, FCF, diluted shares), and common-size margins *relative to peer medians*.
3. Run the accounting quality audit in [references/accounting-and-variant-checklist.md](references/accounting-and-variant-checklist.md): strip non-operating/one-time items, quantify `SBC % of revenue` and `FCF ex-SBC`, check cash conversion (`OCF / Net Income`), and compare historical `ROIC vs. WACC`.
4. **Completion criterion:** 5-year normalized financial diagnostic and peer comparative positioning are complete.

### Phase 3: Strategic Priorities & Quantified "What Is Priced In?"
1. Review latest earnings call transcripts, management guidance, CapEx/R&D roadmap, product launches, partnerships, and M&A via `search_web`.
2. Quantify market-implied expectations using consensus estimates (`market_snapshot.json`) plus the 5-year Reverse DCF solver:
   ```powershell
   uv run <SCRIPTS>/market_data.py reverse-dcf <TICKER> --wacc 0.095 --terminal-growth 0.03 --years 5 --out memory/<TICKER>/reverse_dcf.json
   ```
3. Compare Reverse-DCF implied 5-year FCF growth against historical actuals and consensus to locate exact market mispricing.
4. **Completion criterion:** Strategic priorities and market-implied baseline (`reverse_dcf.json`) are established.

### Phase 4: Variant Thesis Pillars (`T1..Tn`) & Devil's Advocate Stress-Test
1. Formulate 2-4 numbered **Variant Thesis Pillars (`T1`, `T2`, ...)**. Each pillar must state:
   - What consensus/current pricing misunderstands, backed by primary filing or transcript evidence;
   - Exactly which model drivers (`revenue_growth`, `ebit_margin`, `capex_pct_rev`, `premium_discount_pct`, or overridden structural drivers) that pillar moves over the next 5 years, and how it flexes between Bull and Bear cases.
2. Execute the **Bear / Devil's Advocate Check** from [references/accounting-and-variant-checklist.md](references/accounting-and-variant-checklist.md): document top bear counterarguments, dated catalysts, and quantitative thesis-break exit triggers.
3. Save the full primary-source research dossier to `memory/<TICKER>/analyst_dossier.md`.
4. **Completion criterion:** `memory/<TICKER>/analyst_dossier.md` is saved with numbered `T1..Tn` pillars, primary citations, and Bear exit triggers.

### Phase 5: Two-Tier Thesis-Linked 5-Year Excel Valuation
1. Read `memory/client_ips.md` (`buy_min_upside_pct`, `sell_max_upside_pct`) and [references/sector-valuation-guide.md](references/sector-valuation-guide.md) (run `uv run <SCRIPTS>/valuation_excel.py --write-sample-spec` if needed to inspect the exact JSON schema).
2. Assemble `memory/<TICKER>/valuation_spec.json` enforcing the **Two-Tier Assumption Rule**:
   - Set `"ebit_includes_sbc": true` inside `meta` whenever `ebit_margin` is modeled on a GAAP/IFRS (post-SBC) basis so `Memo: Cash Flow ex-SBC` does not double-deduct SBC; keep operating leases excluded from financial debt when EBITDA already deducts rent.
   - Populate `"thesis_pillars"` (`T1..Tn`) with `id`, `title`, `summary`, `impacted_drivers`, `model_impact`, and `bull_bear_flex`.
   - Populate `"assumption_basis"` across all 8 tracked drivers (`revenue_growth`, `ebit_margin`, `capex_pct_rev`, `premium_discount_pct`, `tax_rate`, `da_pct_rev`, `nwc_pct_delta_rev`, `sbc_pct_rev`): link Key Drivers impacted by the thesis via `"basis_type": "thesis"` + `"thesis_ids": ["T1", ...]`, and anchor unchanged/structural drivers via `"basis_type": "historical_or_market"` + `"historical_anchor"` citing 3-5Y SEC actuals.
   - Calibrate explicit 5-year (`len(forecast.years) == 5`) Base, Bull, and Bear paths with Year 5 tapering to normalized terminal reinvestment, uniform dated CAPM `Rf`/`ERP` anchors across same-market peers, time-aligned Comps multiples (`trailing` vs `forward`), and tight Perpetuity-vs-Exit multiple consistency.
3. Build and audit the live-formula `.xlsx` workbook:
   ```powershell
   uv run <SCRIPTS>/valuation_excel.py --spec memory/<TICKER>/valuation_spec.json --out-xlsx Output/models/<TICKER>_valuation.xlsx --out-summary memory/<TICKER>/valuation_summary.json
   ```
4. Verify `memory/<TICKER>/valuation_summary.json`: confirm `formula_audit.status == "PASS"`, `error_cells` is empty, and Base-case `share_price_perpetuity` vs. `share_price_exit_multiple` spread is within `35%` (recalibrating inconsistent terminal inputs transparently if needed). Log completion via `decision_log.py`.
5. **Completion criterion:** `Output/models/<TICKER>_valuation.xlsx` and `memory/<TICKER>/valuation_summary.json` pass all formula, bidirectional `T1..Tn` thesis-linkage, and terminal convergence checks.

### Phase 6: 1-Iteration Master-Agent Rewrite from Verification Feedback (Before Final Delivery)
1. When the independent Cross-Model Verification Agent (`claude-sonnet-5-5-high` via `swarm`) pushes structured feedback (`memory/trail_audit.md` + board post to `@coordinator`) flagging calibration, accounting, `Rf`/`ERP`, Comps time-basis, or thesis gaps (`VERDICT: REVISE_REQUIRED` or actionable analytical improvements):
   - Do **not** bounce findings back to individual researcher subagents. The **master (coordinator) agent directly executes `1` single rewrite iteration** across affected `memory/<TICKER>/analyst_dossier.md` and `memory/<TICKER>/valuation_spec.json` (plus any shared `src/` fixes).
   - Re-run `valuation_excel.py` (`0` error cells), immediately rewrite the paired `memory/<TICKER>/report_draft.md` and re-export the PDF (`audit_report.py --strict-slop --export-pdf`, `0` errors, `0` warnings) per `research-report` Step 4, and log the rewrite in `memory/decisions.tsv`.
2. **Completion criterion:** All actionable reviewer items are incorporated within **`1` master-agent rewrite iteration** and confirmed via a single final sign-off (`VERDICT: PASS`; any residual non-blocking watch items go into `## Attention`, never starting a 2nd rewrite cycle) before final presentation to the user.

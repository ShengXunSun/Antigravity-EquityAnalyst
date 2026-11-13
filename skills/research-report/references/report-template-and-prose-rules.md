# Coverage Report 9-Section Template & Institutional Prose Rules

## Mandatory 9-Section Outline (`memory/<TICKER>/report_draft.md` -> `Output/reports/<TICKER>_report.pdf`)

Use these exact H2 (`##`) section headings (checked by `audit_report.py`):

1. `## 1. Quick Conclusion`
   - Header table: Company Name & Ticker, Exchange, Coverage Rating (`BUY` / `HOLD` / `SELL`), Current Share Price (`$X.XX`), 12-Month Blended Target Price (`$Y.YY`), Implied Upside/Downside (`+Z.Z%`), Market Cap, Enterprise Value, and Valuation Date.
   - One tight paragraph stating the core call and why now.
2. `## 2. Investment Thesis Summary`
   - Crisp bulleted summary of the numbered Variant Thesis Pillars (`T1..Tn`), contrasting what the market prices in (`Reverse DCF` / consensus) against our differentiated view and model impact.
3. `## 3. Stock Selection Rationale & IPS Fit`
   - How `<TICKER>` passed the Hybrid Top-Down + Bottom-Up screening funnel and how its leverage, beta, FCF quality, and implied upside compare against `memory/client_ips.md` hurdles.
4. `## 4. Company Summary`
   - Business model, product/service economics, revenue breakdown by operating segment and geography, customer/supplier dynamics, key unit-economic KPIs, and capital allocation track record (`ROIC` vs. `WACC`, SBC discipline).
5. `## 5. Industry & Competitive Landscape`
   - Addressable market size, cited historical and projected industry CAGR, structural tailwinds/headwinds, competitive moat analysis, and positioning against named peers.
6. `## 6. Financial Summary & Consensus Comparison`
   - Markdown table showing 3-5Y normalized historicals (`10-K`/`20-F`) and 5Y Base-case projections (`Revenue`, `Revenue Growth %`, `Operating Income`, `Operating Margin %`, `EBITDA`, `CapEx`, `Unlevered FCF`, `FCF ex-SBC`).
   - Variant Table comparing **Our 5Y Base Case vs. Market Implied / Consensus**.
7. `## 7. Detailed Variant Thesis` (`audit_report.py` Enforced)
   - Create one H3 subsection per pillar matching `valuation_summary.json` (`### Thesis Pillar T1: <Title>`, `### Thesis Pillar T2: <Title>`, ...).
   - Inside **every** `T1..Tn` subsection, provide:
     1. **Deductive Operational Evidence:** Primary filing (`10-K`/`10-Q`) and transcript facts proving the mechanism without speculation.
     2. **`Model Impact` Block (Mandatory):** Explicitly titled `> **Model Impact (T1):**` (or bullet `**Model Impact:**`) naming every linked model driver in `impacted_drivers` (`revenue_growth`, `ebit_margin`, `capex_pct_rev`, `premium_discount_pct`, etc.), its exact Historical Baseline -> 5-Year Base trajectory, and how it flexes in the Bull vs. Bear scenarios.
8. `## 8. Valuation` (`audit_report.py` Enforced)
   - Explain the selected model (`standard_dcf`, `financials_ddm`, or `reit_affo`), `WACC` / `Cost of Equity` build, and 5-year Perpetuity Growth vs. Exit Multiple cross-check.
   - **Mandatory `Model Assumptions & Basis Table`:** Markdown table with columns `| Assumption | Basis | Historical Anchor | 5Y Base Path | Rationale |` covering all Key Drivers (`Revenue Growth`, `EBIT Margin`, `CapEx % of Rev`, `Comps Premium/Discount`) and Structural Drivers (`Tax Rate`, `D&A %`, `NWC %`, `SBC %`), explicitly citing `Thesis: T1..Tn` vs. `Historical / Market Anchor`.
   - Peer comparable calibration (`EV/EBITDA`, `Forward P/E`, etc.) and Blended Target Price & Scenario Summary table matching `Output/models/<TICKER>_valuation.xlsx`.
9. `## 9. Risks, Catalysts & Exit Triggers`
   - **Key Bearish Risks:** Concrete downside scenarios and how they map to the Bear case (`$Bear_Price`).
   - **Upcoming Catalysts:** Dated events over the next 6-18 months.
   - **Thesis-Break / Upgrade Triggers:** 2-3 measurable KPI or price thresholds that trigger a rating change.

---

## Institutional Plain-Prose Rules (Bundled `unslop` Standard)

`audit_report.py --strict-slop` rejects AI writing tells. Follow these rules throughout:
- **Zero banned AI buzzwords:** Avoid *delve, tapestry, pivotal, testament, underscores, interplay, intricate, vibrant, fostering, garner, serves as, stands as, boasts*. Use plain verbs (*is, has, drives, increases, reduces*).
- **Name every source:** Replace vague attributions (*"experts believe"*, *"industry reports suggest"*, *"observers note"*) with the exact filing, transcript quarter, or institution (*"Per FY2025 Form 10-K, Item 7..."*, *"On the Q3 2026 earnings call, CFO..."*).
- **Punctuation discipline:** Avoid em-dashes (`—`) entirely; use periods, commas, or parentheses.
- **Numbers over adverbs:** Replace *"margins improved significantly"* with *"operating margin expanded 240 bps from 28.1% in FY23 to 30.5% in FY25"*.

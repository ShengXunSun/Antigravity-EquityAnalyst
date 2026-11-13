# Accounting Quality, Peer Benchmarking & Variant Thesis Checklist

Apply every check below during Phases 2-4 of `equity-analyst`.

## 1. GAAP-to-Normalized Earnings & Cash Quality Audit
- **Stock-Based Compensation (SBC):** Report both standard `UFCF` (`OCF - CapEx`) and `FCF ex-SBC` (`OCF - CapEx - SBC`), plus `diluted_shares` 3-5Y CAGR. Flag when SBC exceeds `5%` of revenue or `25%` of OCF without offsetting share count reduction.
- **Cash Conversion:** Compute `OCF / GAAP Net Income` over 3-5 years. Persistent conversion below `0.85x` for non-hypergrowth firms signals aggressive working-capital accruals (check AR growth vs. revenue growth and inventory days).
- **Non-Recurring Adjustments:** Inspect `10-K`/`10-Q` MD&A and footnotes for restructuring, litigation, impairment, acquisition amortization, or tax windfalls so base-year EBIT and effective tax rate reflect recurring operations.
- **Capital Allocation & ROIC:** Compare `NOPAT / Invested Capital` (`ROIC`) against estimated `WACC`. Growth creates shareholder value only when incremental ROIC exceeds WACC.

## 2. Industry-Relative Common-Size Benchmarking
Financial ratios only have meaning relative to industry economics:
- Compare Gross Margin, R&D % of Revenue, SG&A % of Revenue, Operating Margin, CapEx % of Revenue, and Net Debt/EBITDA against the 4-6 company peer table (`peer_comps.json`).
- Distinguish structural business-model differences (e.g., asset-light franchisor vs. company-operated stores; fabless chip designer vs. foundry) before labeling a margin or multiple "cheap" or "expensive".

## 3. Deductive Variant Perception Rule
A valid investment thesis answers three questions without speculation:
1. **Consensus Baseline:** What growth/margin path is embedded in current multiples and `reverse_dcf.json`?
2. **Variant Mechanism:** What specific operational, competitive, or capital-allocation reality does the market underappreciate (or overestimate), and what primary evidence proves it is already underway?
3. **Financial Translation:** Exactly which model driver (`revenue_growth`, `ebit_margin`, `capex_pct_rev`, `wacc`, or peer multiple) moves as a result, and over what timeframe?

## 4. Bear / Devil's Advocate Stress-Test
Before locking `analyst_dossier.md`, answer from a skeptical short/bear perspective:
- What single assumption in our Base case, if wrong by 200-300 bps, wipes out our upside?
- Where do customers, competitors, or regulators have incentives that work against management's plan?
- What observable quarterly KPI or filing metric over the next 2-4 quarters would prove our thesis **broken** (exit trigger)?

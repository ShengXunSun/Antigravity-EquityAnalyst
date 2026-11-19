# Sector Valuation Routing & Two-Tier Thesis Calibration Guide

## 1. Choosing `model_type` & Relative Multiples

| Sector / Business Model | `model_type` | Intrinsic Cash Flow Basis | Discount Rate | Best Relative Multiples | Avoid |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Tech / SaaS / Semis** | `standard_dcf` | Unlevered FCF (plus `FCF ex-SBC` check) | WACC | `ev_to_ebitda`, `forward_pe`, `fcf_yield` (`ev_to_revenue` only if margins are mid-inflection) | Unadjusted P/E when SBC > 10% of rev |
| **Industrials / Consumer / Healthcare** | `standard_dcf` | Unlevered FCF across normalized cycle | WACC | `ev_to_ebitda`, `forward_pe`, `fcf_yield` | Peak-cycle multiples on peak-cycle EBITDA |
| **Banks / Insurance / Lenders** | `financials_ddm` | Distributable Equity Cash Flow / Dividends (`NOPAT - Required Capital Retention`) | Cost of Equity (`Ke`) | `forward_pe` (and `P/TBV` calibrated to `ROTCE / Ke` in report notes) | `EV/EBITDA` and Unlevered DCF (debt is raw operating funding, not capital-structure debt) |
| **Equity REITs** | `reit_affo` | Adjusted FFO (`AFFO` = Cash flow after recurring maintenance CapEx/TI) | WACC / Cost of Equity | `ev_to_ebitda` / `fcf_yield` (representing AFFO yield) | GAAP P/E (distorted by real estate depreciation) |

## 2. Two-Tier Assumption & Thesis Linkage Rule (`valuation_excel.py` Enforced)
Every assumption in `valuation_spec.json` (`assumption_basis`) must declare either `"basis_type": "thesis"` or `"basis_type": "historical_or_market"`:
- **Tier 1 - Key Value Drivers (`revenue_growth`, `ebit_margin`, `capex_pct_rev`, `premium_discount_pct`):** Link to one or more Thesis Pillar IDs (`"thesis_ids": ["T1", ...]`) *whenever a thesis pillar impacts that driver*, and provide a deductive bridge from the operational thesis to the 5-year Base/Bull/Bear trajectory. If no thesis pillar changes one of these drivers, set `"basis_type": "historical_or_market"` and anchor to 3-5Y SEC actuals/consensus. At least one Key Driver must be thesis-driven.
- **Tier 2 - Structural Drivers (`tax_rate`, `da_pct_rev`, `nwc_pct_delta_rev`, `sbc_pct_rev`):** Default to `"basis_type": "historical_or_market"` anchored to 3-5Y SEC filing actuals unless a specific Thesis Pillar (`T1..Tn`) explicitly overrides one.
- **Bidirectional Match:** Every driver listed in `thesis_pillars[i].impacted_drivers` must list that pillar's `T1..Tn` ID in `assumption_basis.<driver>.thesis_ids`, and vice versa. Run `valuation_excel.py --write-sample-spec` anytime to inspect the exact schema.

## 3. Guardrails Against Valuation Manipulation
- **Uniform Dated CAPM Anchors (`Rf` / `ERP`):** Use one shared, dated live sovereign 10-year yield (e.g., `^TNX` for USD models) and one consistent institutional ERP across all same-date/same-currency models in a run.
- **Comps Time-Basis Alignment:** Never apply Yahoo trailing `ev_to_ebitda` directly to forward (`FY+1E`/`FY+2E`) company EBITDA; match trailing multiples to TTM/FY0 metrics, or use NTM-consistent `forward_pe` / consensus forward `EV/EBITDA` (`ev_to_ebitda_ntm_proxy` or primary consensus multiples) across all peers. Do not inflate Comps premiums or exit multiples to rescue a borderline rating.
- **GAAP SBC & Operating-Lease Consistency:** Set `"ebit_includes_sbc": true` in `meta` whenever `ebit_margin` already deducts SBC so `Memo: Cash Flow ex-SBC` does not double-deduct SBC, and exclude operating lease liabilities from `total_debt_m` when EBITDA already expenses operating rent (include finance leases only).
- **5-Year Explicit Horizon & Terminal Run-Rate:** Every DCF/DDM/AFFO model uses an explicit **5-year** projection window (`forecast.years` length = 5). Calibrate Year 5 (`capex_pct_rev` vs. `da_pct_rev` and `ebit_margin`) to normalized steady-state reinvestment so Gordon Growth (`Year5_CF * (1 + g) / (WACC - g)`) does not extrapolate temporary peak-cycle CapEx into perpetuity.
- **Terminal Growth Cap:** Keep `terminal_growth_rate` between `1.5%` and `3.5%` (capped at or below long-term nominal GDP growth and below `WACC - 2.0%`).
- **Perpetuity vs. Exit Multiple Cross-Check:** Row 37 of `WACC & Intrinsic Value` computes the implied exit multiple of Perpetuity TV and implied perpetuity growth of Exit Multiple TV. Keep Base-case Perpetuity and Exit-Multiple share prices within `35%` of each other (ideally well below `25%`), aligning `exit_multiple` with the perpetuity-implied terminal multiple without forcing a target price.
- **Blend Weights:** `blend_weights` (`dcf_perpetuity`, `dcf_exit_multiple`, `relative_comps`) must sum to `1.00` (default `0.40 / 0.25 / 0.35`).

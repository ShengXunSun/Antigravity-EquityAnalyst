# IPS YAML Schema & Risk-Tier Presets

`memory/client_ips.md` begins with YAML frontmatter parsed by `ips_parser.py`. All six top-level sections below are mandatory, and `style_weights` must sum to `1.00` (`±0.02`).

## Required Frontmatter Structure

```yaml
---
ips_version: "1.0"
last_updated: "YYYY-MM-DD"
client_profile:
  name: "Mandate Name"
  horizon_years: 5
  tax_sensitivity: "low | moderate | high"
universe:
  regions: ["US", "ADR_Developed"]
  preferred_sectors: ["Information Technology", "Healthcare", "Industrials"]
  excluded_sectors: []
  excluded_tickers: []
return_and_risk:
  return_objective: "capital_appreciation | total_return | dividend_growth"
  target_annual_return_pct: 12.0
  risk_tolerance: "conservative | moderate | growth | aggressive"
  max_acceptable_drawdown_pct: 25.0
benchmark_and_hurdles:
  benchmark_ticker: "SPY"
  benchmark_name: "S&P 500"
  margin_of_safety_pct: 20.0
  buy_min_upside_pct: 20.0
  sell_max_upside_pct: -5.0
hard_filters:
  min_market_cap_usd_m: 2000
  min_avg_daily_dollar_vol_m: 15
  max_net_debt_to_ebitda: 3.0
  min_interest_coverage: 4.0
  max_beta: 1.4
  require_positive_fcf: true
style_weights:
  quality: 0.35
  valuation: 0.25
  growth: 0.25
  stability: 0.15
---
```

## Recommended Calibration Presets by Risk Tier

| Parameter | `conservative` | `moderate` | `growth` | `aggressive` |
| :--- | :--- | :--- | :--- | :--- |
| **Default Benchmark** | `SCHD` / `VTV` / `SPY` | `SPY` | `SPY` / `QQQ` | `QQQ` / `IWM` |
| **`buy_min_upside_pct`** | `25.0%` | `20.0%` | `15.0%` | `15.0%` |
| **`max_net_debt_to_ebitda`** | `2.0x` | `3.0x` | `3.5x` | `4.5x` |
| **`max_beta`** | `1.10` | `1.40` | `1.75` | `2.20` |
| **`require_positive_fcf`** | `true` | `true` | `true` | `false` |
| **Style Weights (`Q / V / G / S`)** | `0.35 / 0.30 / 0.10 / 0.25` | `0.35 / 0.25 / 0.25 / 0.15` | `0.30 / 0.15 / 0.45 / 0.10` | `0.20 / 0.10 / 0.60 / 0.10` |

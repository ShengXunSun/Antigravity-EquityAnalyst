#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pyyaml>=6.0.1",
# ]
# ///
"""Parse, validate, and initialize hybrid Markdown + YAML Investment Policy Statements (client_ips.md)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

VALID_RISK_TOLERANCES = {"conservative", "moderate", "growth", "aggressive"}

REQUIRED_TOP_KEYS = {
    "client_profile",
    "universe",
    "return_and_risk",
    "benchmark_and_hurdles",
    "hard_filters",
    "style_weights",
}

TEMPLATE_IPS_MD = """---
ips_version: "1.0"
last_updated: "2026-11-13"
client_profile:
  name: "Sample Institutional / Individual Mandate"
  horizon_years: 5
  tax_sensitivity: "moderate"
universe:
  regions: ["US", "ADR_Developed"]
  preferred_sectors: ["Information Technology", "Healthcare", "Industrials"]
  excluded_sectors: ["Tobacco", "Gambling"]
  excluded_tickers: []
return_and_risk:
  return_objective: "capital_appreciation"
  target_annual_return_pct: 12.0
  risk_tolerance: "moderate"
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

# Client Investment Policy Statement (IPS)

## 1. Mandate & Return Objective
Long-term capital appreciation over a 5-year investment horizon targeting 12% annualized total return, outperforming the S&P 500 (`SPY`) on a risk-adjusted basis.

## 2. Risk Tolerance & Downside Guardrails
Moderate risk tolerance. Avoid structurally over-leveraged balance sheets (`Net Debt / EBITDA > 3.0x`) and speculative pre-cash-flow issuers. New Buy initiations require at least a 20% margin of safety to intrinsic value.

## 3. Sector, Geographic & Liquidity Scope
Primary focus on US-listed operating companies and SEC-reporting ADRs (`10-K` / `20-F`) with market capitalization above $2.0B and average daily trading volume above $15M.

## 4. Analytical & Valuation Priorities
Prioritize durable ROIC above WACC, clean GAAP-to-FCF conversion after stock-based compensation, and identifiable variant perception versus consensus expectations.
"""


def extract_yaml_config(markdown_text: str) -> dict[str, Any]:
    """Extract structured config from YAML frontmatter or a ```yaml ips-config block."""
    text = markdown_text.lstrip("\ufeff")
    fm_match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, flags=re.DOTALL)
    if fm_match:
        data = yaml.safe_load(fm_match.group(1))
        if isinstance(data, dict):
            return data

    fenced_match = re.search(
        r"```(?:yaml|yml|json)\s*(?:ips-config)?\r?\n(.*?)\r?\n```",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if fenced_match:
        data = yaml.safe_load(fenced_match.group(1))
        if isinstance(data, dict):
            return data

    raise ValueError(
        "No valid YAML frontmatter (--- ... ---) or fenced ```yaml block found in client_ips.md."
    )


def validate_ips_config(cfg: dict[str, Any]) -> list[str]:
    """Validate IPS dictionary and return a list of validation errors (empty if valid)."""
    errors: list[str] = []
    missing = REQUIRED_TOP_KEYS - set(cfg.keys())
    if missing:
        errors.append(f"Missing required top-level IPS sections: {sorted(missing)}")
        return errors

    rr = cfg.get("return_and_risk") or {}
    rt = str(rr.get("risk_tolerance", "")).lower()
    if rt not in VALID_RISK_TOLERANCES:
        errors.append(
            f"return_and_risk.risk_tolerance must be one of {sorted(VALID_RISK_TOLERANCES)}, got '{rt}'"
        )

    cp = cfg.get("client_profile") or {}
    horizon = cp.get("horizon_years")
    if not isinstance(horizon, (int, float)) or horizon <= 0:
        errors.append("client_profile.horizon_years must be a positive number.")

    bh = cfg.get("benchmark_and_hurdles") or {}
    if not bh.get("benchmark_ticker"):
        errors.append("benchmark_and_hurdles.benchmark_ticker is required (e.g., 'SPY').")
    for hurdle_key in ("margin_of_safety_pct", "buy_min_upside_pct", "sell_max_upside_pct"):
        if not isinstance(bh.get(hurdle_key), (int, float)):
            errors.append(f"benchmark_and_hurdles.{hurdle_key} must be numeric.")

    hf = cfg.get("hard_filters") or {}
    for num_key in ("min_market_cap_usd_m", "min_avg_daily_dollar_vol_m"):
        val = hf.get(num_key)
        if not isinstance(val, (int, float)) or val < 0:
            errors.append(f"hard_filters.{num_key} must be a non-negative number.")

    sw = cfg.get("style_weights") or {}
    expected_styles = {"quality", "valuation", "growth", "stability"}
    if set(sw.keys()) != expected_styles:
        errors.append(f"style_weights must contain exact keys {sorted(expected_styles)}.")
    else:
        total_w = sum(float(sw[k]) for k in expected_styles)
        if abs(total_w - 1.0) > 0.02:
            errors.append(f"style_weights must sum to 1.0 (currently sums to {total_w:.3f}).")

    return errors


def load_ips(path: str | Path) -> dict[str, Any]:
    """Load, parse, and validate client_ips.md."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"IPS file not found: {p}")
    raw = p.read_text(encoding="utf-8")
    cfg = extract_yaml_config(raw)
    errors = validate_ips_config(cfg)
    if errors:
        raise ValueError("Invalid client_ips.md configuration:\n- " + "\n- ".join(errors))
    return cfg


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate or initialize client_ips.md")
    parser.add_argument("path", help="Path to client_ips.md")
    parser.add_argument("--init", action="store_true", help="Write starter template to path")
    parser.add_argument("--force", action="store_true", help="Overwrite existing file with --init")
    parser.add_argument("--json", action="store_true", help="Print parsed IPS config as JSON")
    args = parser.parse_args()

    target = Path(args.path)
    if args.init:
        if target.exists() and not args.force:
            print(f"Error: {target} already exists. Pass --force to overwrite.", file=sys.stderr)
            return 1
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(TEMPLATE_IPS_MD, encoding="utf-8")
        print(f"Initialized IPS template at {target}")
        return 0

    try:
        cfg = load_ips(target)
    except Exception as exc:
        print(f"IPS Validation Failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(cfg, indent=2))
    else:
        print(
            f"IPS Validated OK | Risk: {cfg['return_and_risk']['risk_tolerance']} "
            f"| Benchmark: {cfg['benchmark_and_hurdles']['benchmark_ticker']} "
            f"| Buy Hurdle: >={cfg['benchmark_and_hurdles']['buy_min_upside_pct']}% upside"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

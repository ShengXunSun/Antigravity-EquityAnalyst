#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "yfinance>=0.2.50",
#     "pandas>=2.2.0",
#     "numpy>=1.26.0",
#     "pyyaml>=6.0.1",
# ]
# ///
"""Hybrid Top-Down + Bottom-Up Equity Screener driven by client_ips.md."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

# Allow sibling imports whether invoked from repo root or scripts folder
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ips_parser import load_ips  # noqa: E402
from market_data import fetch_interest_coverage, fetch_snapshot  # noqa: E402

# Balanced liquid US, ADR, and HKEX representative universes across GICS sectors
US_UNIVERSE: list[str] = [
    # Information Technology & Semis
    "AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CRM", "ADBE", "AMD", "ACN", "CSCO",
    "TXN", "QCOM", "INTU", "AMAT", "LRCX", "KLAC", "NOW", "PANW", "SNPS", "ANET", "CRWD", "MU", "DELL", "APP", "PLTR",
    # Communication Services & Digital Platforms
    "GOOGL", "META", "NFLX", "TMUS", "DIS", "VZ", "T", "CMCSA",
    # Consumer Discretionary & Marketplaces
    "AMZN", "TSLA", "HD", "MCD", "NKE", "LOW", "BKNG", "TJX", "SBUX", "CMG", "ORLY", "AZO", "UBER", "DASH", "DECK", "LULU",
    # Consumer Staples
    "COST", "PG", "WMT", "KO", "PEP", "PM", "MDLZ", "CL", "MNST",
    # Healthcare
    "LLY", "UNH", "JNJ", "ABBV", "MRK", "TMO", "ABT", "DHR", "ISRG", "SYK", "AMGN", "VRTX", "REGN",
    # Industrials
    "CAT", "GE", "RTX", "HON", "UNP", "ETN", "DE", "ADP", "LMT", "WM", "ITW", "PH", "TT", "CTAS", "VRT",
    # Financials, Insurance & Payments
    "BRK-B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "SPGI", "BLK", "AXP", "PGR", "CB", "MMC", "KKR", "BX", "SCHW", "PYPL", "HOOD",
    # Energy, Materials, Real Estate, Utilities
    "XOM", "CVX", "COP", "EOG", "SLB", "MPC", "PSX",
    "LIN", "SHW", "APD", "ECL", "FCX", "NEM", "VMC",
    "PLD", "AMT", "EQIX", "WELL", "SPG", "O", "PSA",
    "NEE", "SO", "DUK", "CEG", "AEP", "SRE",
]

ADR_UNIVERSE: list[str] = [
    "TSM", "ASML", "SAP", "SPOT", "NVO", "ARM", "MELI",
]

HK_UNIVERSE: list[str] = [
    # HKEX Technology, Semis & Hardware
    "0981.HK", "0992.HK", "0285.HK", "2382.HK", "1810.HK",
    # HKEX Communication Services & Internet Platforms
    "0700.HK", "9999.HK", "1024.HK", "9888.HK",
    # HKEX Consumer Discretionary & Staples
    "9988.HK", "3690.HK", "9618.HK", "9961.HK", "1211.HK", "2020.HK", "9987.HK",
    "6690.HK", "0300.HK", "9992.HK", "9633.HK", "0291.HK",
    # HKEX Financials, Exchanges & Insurance
    "1299.HK", "0388.HK", "0005.HK", "2318.HK", "3968.HK", "2388.HK",
    # HKEX Industrials & Healthcare
    "0669.HK", "2269.HK", "1093.HK",
]

DEFAULT_UNIVERSE: list[str] = US_UNIVERSE + ADR_UNIVERSE


def _resolve_default_universe(regions: list[str] | None) -> list[str]:
    if not regions:
        return DEFAULT_UNIVERSE
    reg_norm = {str(r).strip().upper() for r in regions if str(r).strip()}
    pool: list[str] = []
    if "US" in reg_norm or "GLOBAL" in reg_norm:
        pool.extend(US_UNIVERSE)
    if any(r in reg_norm for r in ("ADR", "ADR_DEVELOPED", "GLOBAL")):
        pool.extend(ADR_UNIVERSE)
    if any(r in reg_norm for r in ("HK", "HKEX", "HONG KONG", "GLOBAL")):
        pool.extend(HK_UNIVERSE)
    return pool or DEFAULT_UNIVERSE

LEVERAGE_EXEMPT_SECTORS = {"Financial Services", "Financials", "Real Estate"}


def _pct_rank(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    if s.dropna().empty:
        return pd.Series(0.5, index=series.index)
    ranked = s.rank(pct=True, na_option="keep")
    if not higher_is_better:
        ranked = 1.0 - ranked
    return ranked.fillna(0.5)


def run_hybrid_screen(
    ips_path: str | Path,
    tickers: list[str] | None = None,
    macro_tailwinds: dict[str, float] | None = None,
    top_n: int = 5,
    max_workers: int = 8,
) -> dict[str, Any]:
    ips = load_ips(ips_path)
    uni_cfg = ips["universe"]
    default_pool = _resolve_default_universe(uni_cfg.get("regions"))
    universe_list = list(dict.fromkeys(t.upper().strip() for t in (tickers or default_pool) if t.strip()))

    hf = ips["hard_filters"]
    sw = ips["style_weights"]

    excluded_tickers = {t.upper() for t in (uni_cfg.get("excluded_tickers") or [])}
    excluded_sectors = {s.lower() for s in (uni_cfg.get("excluded_sectors") or [])}
    preferred_sectors = {s.lower() for s in (uni_cfg.get("preferred_sectors") or [])}

    raw_snapshots: list[dict[str, Any]] = []
    fetch_errors: list[dict[str, str]] = []

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        fut_map = {pool.submit(fetch_snapshot, tk): tk for tk in universe_list}
        for fut in as_completed(fut_map):
            tk = fut_map[fut]
            try:
                snap = fut.result()
                if snap.get("current_price") is not None:
                    raw_snapshots.append(snap)
                else:
                    fetch_errors.append({"ticker": tk, "error": "Missing current_price"})
            except Exception as exc:
                fetch_errors.append({"ticker": tk, "error": str(exc)})

    survivors: list[dict[str, Any]] = []
    missing_beta_tickers: list[str] = []
    ic_rejected_tickers: list[dict[str, Any]] = []
    rejections: dict[str, int] = {
        "excluded_ticker": 0,
        "excluded_sector_or_industry": 0,
        "below_min_market_cap": 0,
        "below_min_liquidity": 0,
        "missing_beta": 0,
        "above_max_beta": 0,
        "above_max_leverage": 0,
        "below_min_interest_coverage": 0,
        "negative_fcf": 0,
    }

    min_mcap = float(hf.get("min_market_cap_usd_m", 0))
    min_adv = float(hf.get("min_avg_daily_dollar_vol_m", 0))
    max_beta = hf.get("max_beta")
    max_nd_ebitda = hf.get("max_net_debt_to_ebitda")
    min_int_cov = hf.get("min_interest_coverage")
    req_pos_fcf = bool(hf.get("require_positive_fcf", False))

    for s in raw_snapshots:
        tk = s["ticker"]
        sec = (s.get("sector") or "").strip()
        ind = (s.get("industry") or "").strip()
        mcap = s.get("market_cap_usd_m") or 0.0
        adv = s.get("avg_daily_dollar_vol_m") or 0.0
        beta = s.get("beta")
        ttm = s["fundamentals_ttm"]
        mult = s["multiples"]
        nd_ebitda = ttm.get("net_debt_to_ebitda")
        fcf = ttm.get("free_cash_flow")

        if tk in excluded_tickers:
            rejections["excluded_ticker"] += 1
            continue
        if any(ex in sec.lower() or ex in ind.lower() for ex in excluded_sectors):
            rejections["excluded_sector_or_industry"] += 1
            continue
        if mcap < min_mcap:
            rejections["below_min_market_cap"] += 1
            continue
        if adv < min_adv:
            rejections["below_min_liquidity"] += 1
            continue
        if max_beta is not None:
            if beta is None:
                rejections["missing_beta"] += 1
                missing_beta_tickers.append(tk)
                continue
            if beta > float(max_beta):
                rejections["above_max_beta"] += 1
                continue
        if (
            max_nd_ebitda is not None
            and sec not in LEVERAGE_EXEMPT_SECTORS
            and nd_ebitda is not None
            and nd_ebitda > float(max_nd_ebitda)
        ):
            rejections["above_max_leverage"] += 1
            continue
        if req_pos_fcf and sec not in LEVERAGE_EXEMPT_SECTORS and (fcf is None or fcf <= 0):
            rejections["negative_fcf"] += 1
            continue

        survivors.append(
            {
                "ticker": tk,
                "name": s["short_name"],
                "sector": sec,
                "industry": ind,
                "price": s["current_price"],
                "market_cap_usd_m": mcap,
                "adv_usd_m": adv,
                "beta": beta,
                "roe": ttm.get("return_on_equity"),
                "operating_margin": ttm.get("operating_margins"),
                "gross_margin": ttm.get("gross_margins"),
                "revenue_growth": ttm.get("revenue_growth_yoy"),
                "earnings_growth": ttm.get("earnings_growth_yoy"),
                "net_debt_to_ebitda": nd_ebitda,
                "current_ratio": ttm.get("current_ratio"),
                "forward_pe": mult.get("forward_pe"),
                "ev_to_ebitda": mult.get("ev_to_ebitda"),
                "peg_ratio": mult.get("peg_ratio"),
                "fcf_yield": mult.get("fcf_yield"),
                "consensus_target": s["consensus"].get("target_mean_price"),
            }
        )

    if not survivors:
        return {
            "universe_evaluated": len(raw_snapshots),
            "fetch_errors": fetch_errors,
            "hard_filter_rejections": rejections,
            "survivors_count": 0,
            "finalists": [],
        }

    df = pd.DataFrame(survivors)

    # Pillar 1: Quality (ROE, Operating Margin, Gross Margin)
    df["q_score"] = (
        0.40 * _pct_rank(df["roe"], True)
        + 0.40 * _pct_rank(df["operating_margin"], True)
        + 0.20 * _pct_rank(df["gross_margin"], True)
    )

    # Pillar 2: Valuation (FCF Yield, inverse Forward PE, inverse EV/EBITDA)
    df["v_score"] = (
        0.40 * _pct_rank(df["fcf_yield"], True)
        + 0.35 * _pct_rank(df["forward_pe"], False)
        + 0.25 * _pct_rank(df["ev_to_ebitda"], False)
    )

    # Pillar 3: Growth (Revenue Growth, Earnings Growth)
    df["g_score"] = (
        0.55 * _pct_rank(df["revenue_growth"], True)
        + 0.45 * _pct_rank(df["earnings_growth"], True)
    )

    # Pillar 4: Stability (Low Net Debt/EBITDA, Low Beta, Healthy Current Ratio)
    df["s_score"] = (
        0.45 * _pct_rank(df["net_debt_to_ebitda"], False)
        + 0.35 * _pct_rank(df["beta"], False)
        + 0.20 * _pct_rank(df["current_ratio"], True)
    )

    df["bottom_up_score"] = (
        float(sw["quality"]) * df["q_score"]
        + float(sw["valuation"]) * df["v_score"]
        + float(sw["growth"]) * df["g_score"]
        + float(sw["stability"]) * df["s_score"]
    )

    # Top-Down Macro Tailwind & IPS Preferred Sector Overlay (bounded [-0.15, +0.15] so bottom-up winners still surface)
    tailwind_map = {k.lower(): float(v) for k, v in (macro_tailwinds or {}).items()}

    def _top_down_adj(row: pd.Series) -> float:
        sec_l = str(row["sector"]).lower()
        ind_l = str(row["industry"]).lower()
        adj = 0.0
        if preferred_sectors and any(ps in sec_l or ps in ind_l for ps in preferred_sectors):
            adj += 0.05
        for key, delta in tailwind_map.items():
            if key in sec_l or key in ind_l:
                adj += delta
                break
        return max(-0.15, min(0.15, adj))

    df["top_down_adjustment"] = df.apply(_top_down_adj, axis=1)
    df["composite_score"] = (df["bottom_up_score"] + df["top_down_adjustment"]).round(4)

    df = df.sort_values("composite_score", ascending=False).reset_index(drop=True)

    # Enforce min_interest_coverage on top non-financial contenders before picking finalists/top-20
    top_pool_n = min(len(df), max(top_n * 6, 30))
    cov_map: dict[str, float | None] = {}
    if min_int_cov is not None and top_pool_n > 0:
        check_tks = [
            str(df.iloc[i]["ticker"])
            for i in range(top_pool_n)
            if str(df.iloc[i]["sector"]) not in LEVERAGE_EXEMPT_SECTORS
        ]
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            fut_cov = {pool.submit(fetch_interest_coverage, tk): tk for tk in check_tks}
            for fut in as_completed(fut_cov):
                tk_c = fut_cov[fut]
                try:
                    cov_map[tk_c] = fut.result()
                except Exception:
                    cov_map[tk_c] = None

    filtered_recs: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        rec = row.where(pd.notnull(row), None).to_dict()
        tk_r = str(rec["ticker"])
        sec_r = str(rec.get("sector") or "")
        cov = cov_map.get(tk_r)
        rec["interest_coverage"] = cov
        if (
            min_int_cov is not None
            and sec_r not in LEVERAGE_EXEMPT_SECTORS
            and cov is not None
            and cov < float(min_int_cov)
        ):
            rejections["below_min_interest_coverage"] += 1
            ic_rejected_tickers.append({"ticker": tk_r, "interest_coverage": cov})
            continue
        for sc in ("q_score", "v_score", "g_score", "s_score", "bottom_up_score", "top_down_adjustment", "composite_score"):
            if rec.get(sc) is not None:
                rec[sc] = round(float(rec[sc]), 4)
        filtered_recs.append(rec)

    # Cap max 2 finalists per identical industry to avoid single-industry crowding
    finalist_rows: list[dict[str, Any]] = []
    industry_counts: dict[str, int] = {}
    for rec in filtered_recs:
        ind_name = str(rec["industry"] or "Unknown")
        if industry_counts.get(ind_name, 0) >= 2:
            continue
        industry_counts[ind_name] = industry_counts.get(ind_name, 0) + 1
        finalist_rows.append(rec)
        if len(finalist_rows) >= top_n:
            break

    top_20 = filtered_recs[:20]
    return {
        "ips_risk_tolerance": ips["return_and_risk"]["risk_tolerance"],
        "ips_benchmark": ips["benchmark_and_hurdles"]["benchmark_ticker"],
        "style_weights": sw,
        "macro_tailwinds_applied": macro_tailwinds or {},
        "universe_requested": len(universe_list),
        "universe_evaluated": len(raw_snapshots),
        "fetch_errors_count": len(fetch_errors),
        "missing_beta_tickers": sorted(missing_beta_tickers),
        "interest_coverage_rejected": ic_rejected_tickers,
        "hard_filter_rejections": rejections,
        "survivors_count": len(filtered_recs),
        "finalists": finalist_rows,
        "top_20_leaderboard": top_20,
    }


def render_funnel_markdown(res: dict[str, Any]) -> str:
    lines = [
        "# Hybrid Equity Screening Funnel Report",
        "",
        f"- **Risk Mandate:** `{res['ips_risk_tolerance']}` | **Benchmark:** `{res['ips_benchmark']}`",
        f"- **Universe Evaluated:** {res['universe_evaluated']} / {res['universe_requested']} tickers",
        f"- **IPS Hard-Filter Survivors:** {res['survivors_count']} tickers",
        f"- **Style Weights:** Quality `{res['style_weights']['quality']:.0%}`, "
        f"Valuation `{res['style_weights']['valuation']:.0%}`, "
        f"Growth `{res['style_weights']['growth']:.0%}`, "
        f"Stability `{res['style_weights']['stability']:.0%}`",
        "",
        "## Hard-Filter Attrition Breakdown",
        "",
        "| Filter Rule | Excluded Count |",
        "| :--- | ---: |",
    ]
    for rule, cnt in res["hard_filter_rejections"].items():
        lines.append(f"| `{rule}` | {cnt} |")

    lines.extend(
        [
            "",
            "## Screened Finalists",
            "",
            "| Rank | Ticker | Company | Sector / Industry | MCap ($M) | Fwd P/E | FCF Yield | Op Margin | Rev YoY | Bottom-Up | Macro Adj | Composite |",
            "| ---: | :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for idx, f in enumerate(res["finalists"], start=1):
        fpe = f"{f['forward_pe']:.1f}x" if f.get("forward_pe") else "N/A"
        fcfy = f"{f['fcf_yield'] * 100:.1f}%" if f.get("fcf_yield") is not None else "N/A"
        opm = f"{f['operating_margin'] * 100:.1f}%" if f.get("operating_margin") is not None else "N/A"
        revy = f"{f['revenue_growth'] * 100:.1f}%" if f.get("revenue_growth") is not None else "N/A"
        mcap = f"{f['market_cap_usd_m']:,.0f}" if f.get("market_cap_usd_m") else "N/A"
        lines.append(
            f"| {idx} | **{f['ticker']}** | {f['name']} | {f['sector']} / {f['industry']} "
            f"| {mcap} | {fpe} | {fcfy} | {opm} | {revy} "
            f"| {f['bottom_up_score']:.3f} | {f['top_down_adjustment']:+.3f} | **{f['composite_score']:.3f}** |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Hybrid Top-Down + Bottom-Up Equity Screener")
    parser.add_argument("--ips", default="memory/client_ips.md", help="Path to client_ips.md")
    parser.add_argument("--tickers", nargs="*", help="Optional explicit ticker universe")
    parser.add_argument("--tickers-file", help="Optional text/JSON file with candidate tickers")
    parser.add_argument("--macro-json", help="Optional JSON file mapping sector/industry -> tailwind [-0.15, +0.15]")
    parser.add_argument("--top-n", type=int, default=5, help="Number of finalists to output")
    parser.add_argument("--out-json", default="memory/screening_results.json")
    parser.add_argument("--out-md", default="memory/screening_funnel.md")
    args = parser.parse_args()

    tickers = args.tickers
    if args.tickers_file:
        tf = Path(args.tickers_file)
        raw = tf.read_text(encoding="utf-8").strip()
        tickers = json.loads(raw) if raw.startswith("[") else [
            t.strip() for t in raw.replace(",", "\n").splitlines() if t.strip()
        ]

    macro_map = None
    if args.macro_json:
        macro_map = json.loads(Path(args.macro_json).read_text(encoding="utf-8"))

    try:
        res = run_hybrid_screen(
            ips_path=args.ips,
            tickers=tickers,
            macro_tailwinds=macro_map,
            top_n=args.top_n,
        )
        out_j = Path(args.out_json)
        out_j.parent.mkdir(parents=True, exist_ok=True)
        out_j.write_text(json.dumps(res, indent=2), encoding="utf-8")

        out_m = Path(args.out_md)
        out_m.parent.mkdir(parents=True, exist_ok=True)
        out_m.write_text(render_funnel_markdown(res), encoding="utf-8")

        print(
            f"Screener complete: {res['survivors_count']}/{res['universe_evaluated']} passed hard filters -> "
            f"{len(res['finalists'])} finalists: {[f['ticker'] for f in res['finalists']]}"
        )
        print(f"Saved JSON: {out_j} | Markdown: {out_m}")
    except Exception as exc:
        print(f"Screener error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

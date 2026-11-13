#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "yfinance>=0.2.50",
#     "pandas>=2.2.0",
#     "numpy>=1.26.0",
# ]
# ///
"""Market snapshot, consensus estimates, Reverse DCF solver, peer comps, and benchmark sanity check."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

# Store yfinance SQLite cache inside workspace memory/.cache to avoid temp lock collisions
_YF_CACHE = Path("memory/.cache/yfinance")
_YF_CACHE.mkdir(parents=True, exist_ok=True)
try:
    yf.set_tz_cache_location(str(_YF_CACHE))
except Exception:
    pass


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def fetch_snapshot(ticker: str) -> dict[str, Any]:
    info: dict[str, Any] = {}
    for attempt in range(3):
        try:
            tk = yf.Ticker(ticker.upper())
            info = tk.info or {}
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(0.25 * (attempt + 1))

    price = _safe_float(info.get("currentPrice") or info.get("regularMarketPrice"))
    mcap = _safe_float(info.get("marketCap"))
    ev = _safe_float(info.get("enterpriseValue"))
    fcf = _safe_float(info.get("freeCashflow"))
    ocf = _safe_float(info.get("operatingCashflow"))
    ebitda = _safe_float(info.get("ebitda"))
    total_debt = _safe_float(info.get("totalDebt")) or 0.0
    total_cash = _safe_float(info.get("totalCash")) or 0.0
    net_debt = total_debt - total_cash
    avg_vol = _safe_float(info.get("averageVolume"))
    adv_usd_m = ((price * avg_vol) / 1e6) if (price and avg_vol) else None
    fcf_yield = (fcf / mcap) if (fcf is not None and mcap and mcap > 0) else None
    nd_ebitda = (net_debt / ebitda) if (ebitda and ebitda > 0) else None

    return {
        "ticker": ticker.upper(),
        "short_name": info.get("shortName") or info.get("longName") or ticker.upper(),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "quote_type": info.get("quoteType"),
        "currency": info.get("currency", "USD"),
        "current_price": price,
        "market_cap": mcap,
        "market_cap_usd_m": round(mcap / 1e6, 2) if mcap else None,
        "enterprise_value": ev,
        "avg_daily_dollar_vol_m": round(adv_usd_m, 2) if adv_usd_m else None,
        "beta": _safe_float(info.get("beta")),
        "52w_high": _safe_float(info.get("fiftyTwoWeekHigh")),
        "52w_low": _safe_float(info.get("fiftyTwoWeekLow")),
        "multiples": {
            "trailing_pe": _safe_float(info.get("trailingPE")),
            "forward_pe": _safe_float(info.get("forwardPE")),
            "peg_ratio": _safe_float(info.get("pegRatio") or info.get("trailingPegRatio")),
            "ev_to_ebitda": _safe_float(info.get("enterpriseToEbitda")),
            "ev_to_revenue": _safe_float(info.get("enterpriseToRevenue")),
            "price_to_book": _safe_float(info.get("priceToBook")),
            "dividend_yield": _safe_float(info.get("dividendYield")),
            "fcf_yield": round(fcf_yield, 4) if fcf_yield is not None else None,
        },
        "fundamentals_ttm": {
            "total_revenue": _safe_float(info.get("totalRevenue")),
            "revenue_growth_yoy": _safe_float(info.get("revenueGrowth")),
            "earnings_growth_yoy": _safe_float(info.get("earningsGrowth")),
            "gross_margins": _safe_float(info.get("grossMargins")),
            "ebitda_margins": _safe_float(info.get("ebitdaMargins")),
            "operating_margins": _safe_float(info.get("operatingMargins")),
            "profit_margins": _safe_float(info.get("profitMargins")),
            "return_on_equity": _safe_float(info.get("returnOnEquity")),
            "return_on_assets": _safe_float(info.get("returnOnAssets")),
            "ebitda": ebitda,
            "operating_cash_flow": ocf,
            "free_cash_flow": fcf,
            "total_cash": total_cash,
            "total_debt": total_debt,
            "net_debt": net_debt,
            "net_debt_to_ebitda": round(nd_ebitda, 2) if nd_ebitda is not None else None,
            "current_ratio": _safe_float(info.get("currentRatio")),
            "shares_outstanding": _safe_float(info.get("sharesOutstanding")),
        },
        "consensus": {
            "target_mean_price": _safe_float(info.get("targetMeanPrice")),
            "target_median_price": _safe_float(info.get("targetMedianPrice")),
            "target_high_price": _safe_float(info.get("targetHighPrice")),
            "target_low_price": _safe_float(info.get("targetLowPrice")),
            "recommendation_key": info.get("recommendationKey"),
            "recommendation_mean": _safe_float(info.get("recommendationMean")),
            "number_of_analyst_opinions": info.get("numberOfAnalystOpinions"),
            "forward_eps": _safe_float(info.get("forwardEps")),
            "trailing_eps": _safe_float(info.get("trailingEps")),
        },
    }


def solve_reverse_dcf(
    ticker: str,
    wacc: float = 0.095,
    terminal_growth: float = 0.03,
    years: int = 5,
    base_fcf_override: float | None = None,
) -> dict[str, Any]:
    """Solve for the implied annual FCF CAGR over `years` that equates DCF EV to current Market EV."""
    snap = fetch_snapshot(ticker)
    ev = snap["enterprise_value"]
    ttm = snap["fundamentals_ttm"]
    base_fcf = base_fcf_override if base_fcf_override is not None else ttm.get("free_cash_flow")
    rev = ttm.get("total_revenue")

    if not ev or ev <= 0:
        raise ValueError(f"Valid positive Enterprise Value unavailable for {ticker} (got {ev}).")
    if not base_fcf or base_fcf <= 0:
        # Fallback to 10% normalized FCF margin on TTM revenue when TTM FCF is depressed/missing
        if rev and rev > 0:
            base_fcf = rev * 0.10
            fcf_note = "TTM FCF non-positive/unavailable; used normalized 10% FCF margin on TTM revenue."
        else:
            raise ValueError(f"Cannot run Reverse DCF for {ticker}: no positive FCF or Revenue.")
    else:
        fcf_note = "Used TTM Free Cash Flow from market snapshot."

    if wacc <= terminal_growth + 0.005:
        raise ValueError("WACC must exceed terminal_growth by at least 50 bps.")

    def _ev_at_growth(g: float) -> float:
        pv_cf = 0.0
        cf = base_fcf
        for t in range(1, years + 1):
            cf = cf * (1.0 + g)
            pv_cf += cf / ((1.0 + wacc) ** t)
        tv = (cf * (1.0 + terminal_growth)) / (wacc - terminal_growth)
        pv_tv = tv / ((1.0 + wacc) ** years)
        return pv_cf + pv_tv

    lo, hi = -0.35, 1.25
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if _ev_at_growth(mid) < ev:
            lo = mid
        else:
            hi = mid
    implied_cagr = 0.5 * (lo + hi)

    return {
        "ticker": ticker.upper(),
        "current_price": snap["current_price"],
        "enterprise_value": ev,
        "base_fcf_used": round(base_fcf, 2),
        "base_fcf_note": fcf_note,
        "wacc": wacc,
        "terminal_growth": terminal_growth,
        "horizon_years": years,
        "implied_fcf_cagr": round(implied_cagr, 4),
        "implied_fcf_cagr_pct": round(implied_cagr * 100.0, 2),
        "consensus_revenue_growth_yoy": ttm.get("revenue_growth_yoy"),
        "consensus_target_mean": snap["consensus"]["target_mean_price"],
    }


def build_peer_comps(tickers: list[str]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for t in tickers:
        s = fetch_snapshot(t)
        m = s["multiples"]
        f = s["fundamentals_ttm"]
        rows.append(
            {
                "ticker": s["ticker"],
                "name": s["short_name"],
                "market_cap_usd_m": s["market_cap_usd_m"],
                "enterprise_value_usd_m": round(s["enterprise_value"] / 1e6, 2)
                if s["enterprise_value"]
                else None,
                "revenue_growth_yoy": f["revenue_growth_yoy"],
                "ebitda_margin": f["ebitda_margins"],
                "operating_margin": f["operating_margins"],
                "roe": f["return_on_equity"],
                "net_debt_to_ebitda": f["net_debt_to_ebitda"],
                "trailing_pe": m["trailing_pe"],
                "forward_pe": m["forward_pe"],
                "peg_ratio": m["peg_ratio"],
                "ev_to_ebitda": m["ev_to_ebitda"],
                "ev_to_revenue": m["ev_to_revenue"],
                "price_to_book": m["price_to_book"],
                "fcf_yield": m["fcf_yield"],
            }
        )

    df = pd.DataFrame(rows)
    stat_cols = [
        "revenue_growth_yoy",
        "ebitda_margin",
        "operating_margin",
        "roe",
        "net_debt_to_ebitda",
        "trailing_pe",
        "forward_pe",
        "peg_ratio",
        "ev_to_ebitda",
        "ev_to_revenue",
        "price_to_book",
        "fcf_yield",
    ]
    summary: dict[str, dict[str, float | None]] = {"mean": {}, "median": {}, "p25": {}, "p75": {}}
    for col in stat_cols:
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if series.empty:
            for k in summary:
                summary[k][col] = None
        else:
            summary["mean"][col] = round(float(series.mean()), 4)
            summary["median"][col] = round(float(series.median()), 4)
            summary["p25"][col] = round(float(series.quantile(0.25)), 4)
            summary["p75"][col] = round(float(series.quantile(0.75)), 4)

    return {
        "tickers": [r["ticker"] for r in rows],
        "peers": rows,
        "summary_statistics": summary,
    }


def run_benchmark_sanity_check(
    tickers: list[str], benchmark: str = "SPY", years: int = 5
) -> dict[str, Any]:
    """Compare equal-weight basket of current finalists vs benchmark with explicit survivorship-bias warning."""
    clean_tickers = [t.upper() for t in tickers]
    bm = benchmark.upper()
    all_syms = list(dict.fromkeys(clean_tickers + [bm]))

    hist = yf.download(
        all_syms,
        period=f"{years}y",
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if hist.empty:
        raise ValueError("No historical price data returned from yfinance.")

    closes = hist["Close"] if "Close" in hist else hist
    if isinstance(closes, pd.Series):
        closes = closes.to_frame(name=all_syms[0])

    daily_ret = closes.pct_change(fill_method=None).dropna(how="all")
    avail_basket = [
        t for t in clean_tickers if t in daily_ret.columns and int(daily_ret[t].notna().sum()) > 20
    ]
    if not avail_basket or bm not in daily_ret.columns or int(daily_ret[bm].notna().sum()) <= 20:
        raise ValueError(f"Missing valid price series for basket {avail_basket} or benchmark {bm}.")

    aligned = daily_ret[avail_basket + [bm]].dropna(how="any")
    if len(aligned) < 20:
        raise ValueError(f"Insufficient overlapping trading days ({len(aligned)}) for sanity check.")
    basket_ret = aligned[avail_basket].mean(axis=1)
    bm_ret = aligned[bm]

    def _stats(r: pd.Series) -> dict[str, float]:
        n_days = len(r)
        cum = (1.0 + r).cumprod()
        total_ret = float(cum.iloc[-1] - 1.0)
        cagr = float(cum.iloc[-1] ** (252.0 / max(n_days, 1)) - 1.0)
        vol = float(r.std() * np.sqrt(252.0))
        sharpe = float(((r.mean() * 252.0) - 0.04) / vol) if vol > 0 else 0.0
        running_max = cum.cummax()
        max_dd = float(((cum / running_max) - 1.0).min())
        return {
            "total_return_pct": round(total_ret * 100.0, 2),
            "cagr_pct": round(cagr * 100.0, 2),
            "annualized_vol_pct": round(vol * 100.0, 2),
            "sharpe_ratio_rf4pct": round(sharpe, 2),
            "max_drawdown_pct": round(max_dd * 100.0, 2),
        }

    cov = float(np.cov(basket_ret, bm_ret)[0, 1])
    bm_var = float(np.var(bm_ret))
    realized_beta = round(cov / bm_var, 2) if bm_var > 0 else None

    return {
        "survivorship_and_lookahead_warning": (
            "WARNING: This sanity check evaluates backward price history of TODAY's surviving finalists. "
            "It contains survivorship and look-ahead bias (delisted/failed issuers are absent and current "
            "fundamentals were used for selection). Use strictly to inspect historical volatility, beta, "
            "and drawdown behavior relative to the benchmark—never as a predictive strategy backtest."
        ),
        "period_years": years,
        "trading_days_evaluated": int(len(aligned)),
        "basket_tickers": avail_basket,
        "benchmark_ticker": bm,
        "realized_basket_beta_vs_benchmark": realized_beta,
        "equal_weight_basket": _stats(basket_ret),
        "benchmark": _stats(bm_ret),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Market data, Reverse DCF, Comps, and Sanity Check")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_snap = sub.add_parser("snapshot", help="Fetch market snapshot & consensus for a ticker")
    p_snap.add_argument("ticker")
    p_snap.add_argument("--out")

    p_rdcf = sub.add_parser("reverse-dcf", help="Solve implied FCF CAGR priced into current EV")
    p_rdcf.add_argument("ticker")
    p_rdcf.add_argument("--wacc", type=float, default=0.095)
    p_rdcf.add_argument("--terminal-growth", type=float, default=0.03)
    p_rdcf.add_argument("--years", type=int, default=5)
    p_rdcf.add_argument("--base-fcf", type=float, default=None)
    p_rdcf.add_argument("--out")

    p_comps = sub.add_parser("comps", help="Build peer comparable multiples table")
    p_comps.add_argument("tickers", nargs="+")
    p_comps.add_argument("--out")

    p_sanity = sub.add_parser("sanity-check", help="Run survivorship-flagged benchmark check")
    p_sanity.add_argument("tickers", nargs="+")
    p_sanity.add_argument("--benchmark", default="SPY")
    p_sanity.add_argument("--years", type=int, default=5)
    p_sanity.add_argument("--out")

    args = parser.parse_args()
    try:
        if args.cmd == "snapshot":
            res = fetch_snapshot(args.ticker)
        elif args.cmd == "reverse-dcf":
            res = solve_reverse_dcf(
                args.ticker,
                wacc=args.wacc,
                terminal_growth=args.terminal_growth,
                years=args.years,
                base_fcf_override=args.base_fcf,
            )
        elif args.cmd == "comps":
            res = build_peer_comps(args.tickers)
        elif args.cmd == "sanity-check":
            res = run_benchmark_sanity_check(
                args.tickers, benchmark=args.benchmark, years=args.years
            )
        else:
            raise ValueError(f"Unknown command: {args.cmd}")

        payload = json.dumps(res, indent=2)
        if getattr(args, "out", None):
            out_p = Path(args.out)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(payload, encoding="utf-8")
            print(f"Wrote {args.cmd} output to {out_p}")
        else:
            print(payload)
    except Exception as exc:
        print(f"Market data error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

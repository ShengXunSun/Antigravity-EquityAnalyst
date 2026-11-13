#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests>=2.31.0",
#     "beautifulsoup4>=4.12.0",
#     "lxml>=5.0.0",
# ]
# ///
"""SEC EDGAR API client for authoritative 10-K/20-F/10-Q/8-K filings and XBRL companyfacts."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

DEFAULT_USER_AGENT = os.environ.get(
    "SEC_USER_AGENT", "FinanceBroResearch/1.0 (equity-research@financebro.org)"
)
CACHE_DIR = Path("memory/.cache/edgar")

# Ordered XBRL concept priority lists (US-GAAP + IFRS for 20-F ADRs)
FLOW_CONCEPTS: dict[str, list[str]] = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
        "RevenuesNetOfInterestExpense",
        "TotalRevenuesAndOtherIncome",
        "Revenue",
    ],
    "gross_profit": ["GrossProfit"],
    "cost_of_revenue": [
        "CostOfGoodsAndServicesSold",
        "CostOfRevenue",
        "CostOfGoodsSold",
    ],
    "rd_expense": [
        "ResearchAndDevelopmentExpense",
        "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost",
    ],
    "sga_expense": ["SellingGeneralAndAdministrativeExpense"],
    "operating_income": [
        "OperatingIncomeLoss",
        "ProfitLossFromOperatingActivities",
    ],
    "pretax_income": [
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        "ProfitLossBeforeTax",
    ],
    "income_tax": ["IncomeTaxExpenseBenefit", "IncomeTaxesPaidNet"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "operating_cash_flow": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
        "CashFlowsFromUsedInOperatingActivities",
    ],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
        "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
    ],
    "sbc": [
        "ShareBasedCompensation",
        "AllocatedShareBasedCompensationExpense",
        "ExpenseFromShareBasedPaymentTransactionsInWhichGoodsOrServicesReceivedDidNotQualifyForRecognitionAsAssets",
    ],
    "da": [
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
        "Depreciation",
    ],
    "interest_expense": [
        "InterestExpense",
        "InterestExpenseDebt",
        "InterestAndDebtExpense",
    ],
    "dividends_paid": [
        "PaymentsOfDividendsCommonStock",
        "PaymentsOfDividends",
        "DividendsPaid",
    ],
    "share_repurchases": [
        "PaymentsForRepurchaseOfCommonStock",
    ],
    "diluted_shares_flow": [
        "WeightedAverageNumberOfDilutedSharesOutstanding",
    ],
}

INSTANT_CONCEPTS: dict[str, list[str]] = {
    "cash_and_equivalents": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsAndShortTermInvestments",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        "CashAndCashEquivalents",
    ],
    "short_term_investments": [
        "MarketableSecuritiesCurrent",
        "ShortTermInvestments",
        "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
    ],
    "total_current_assets": ["AssetsCurrent", "CurrentAssets"],
    "total_assets": ["Assets"],
    "short_term_debt": [
        "DebtCurrent",
        "LongTermDebtCurrent",
        "ShortTermBorrowings",
    ],
    "long_term_debt": [
        "LongTermDebtNoncurrent",
        "LongTermDebt",
        "LongTermDebtAndCapitalLeaseObligations",
    ],
    "total_current_liabilities": ["LiabilitiesCurrent", "CurrentLiabilities"],
    "total_liabilities": ["Liabilities"],
    "stockholders_equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        "EquityAttributableToOwnersOfParent",
        "Equity",
    ],
    "common_shares_out": [
        "CommonStockSharesOutstanding",
        "EntityCommonStockSharesOutstanding",
    ],
}

ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}


class EdgarClient:
    def __init__(self, user_agent: str = DEFAULT_USER_AGENT, cache_dir: Path = CACHE_DIR):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept-Encoding": "gzip, deflate",
            }
        )
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._last_req = 0.0

    def _get_json(self, url: str, cache_name: str | None = None, ttl_hours: int = 24) -> dict[str, Any]:
        if cache_name:
            cp = self.cache_dir / cache_name
            if cp.exists():
                age_hours = (time.time() - cp.stat().st_mtime) / 3600.0
                if age_hours < ttl_hours:
                    return json.loads(cp.read_text(encoding="utf-8"))

        elapsed = time.time() - self._last_req
        if elapsed < 0.12:
            time.sleep(0.12 - elapsed)

        resp = self.session.get(url, timeout=30)
        self._last_req = time.time()
        resp.raise_for_status()
        data = resp.json()

        if cache_name:
            cp = self.cache_dir / cache_name
            cp.write_text(json.dumps(data), encoding="utf-8")
        return data

    def _get_text(self, url: str) -> str:
        elapsed = time.time() - self._last_req
        if elapsed < 0.12:
            time.sleep(0.12 - elapsed)
        resp = self.session.get(url, timeout=45)
        self._last_req = time.time()
        resp.raise_for_status()
        return resp.text

    def resolve_cik(self, ticker: str) -> tuple[str, str]:
        """Resolve ticker to (10-digit zero-padded CIK, official company title)."""
        tickers_map = self._get_json(
            "https://www.sec.gov/files/company_tickers.json",
            cache_name="company_tickers.json",
            ttl_hours=72,
        )
        norm = ticker.upper().strip()
        alt = norm.replace(".", "-")
        for entry in tickers_map.values():
            t = str(entry.get("ticker", "")).upper()
            if t in (norm, alt):
                cik_str = str(entry["cik_str"]).zfill(10)
                return cik_str, str(entry.get("title", norm))
        raise ValueError(f"Ticker '{ticker}' not found in SEC EDGAR company_tickers.json")

    def list_filings(
        self, ticker: str, forms: list[str] | None = None, limit: int = 12
    ) -> dict[str, Any]:
        cik, title = self.resolve_cik(ticker)
        sub = self._get_json(
            f"https://data.sec.gov/submissions/CIK{cik}.json",
            cache_name=f"submissions_{cik}.json",
            ttl_hours=12,
        )
        recent = sub.get("filings", {}).get("recent", {})
        wanted = {f.upper().strip() for f in forms} if forms else {"10-K", "20-F", "10-Q", "8-K"}

        items: list[dict[str, Any]] = []
        form_list = recent.get("form", [])
        cik_int = str(int(cik))
        for i, f_type in enumerate(form_list):
            if f_type.upper() not in wanted:
                continue
            acc = recent["accessionNumber"][i]
            acc_no_dash = acc.replace("-", "")
            doc = recent["primaryDocument"][i]
            items.append(
                {
                    "form": f_type,
                    "filing_date": recent["filingDate"][i],
                    "report_date": recent.get("reportDate", [""])[i],
                    "accession_number": acc,
                    "primary_document": doc,
                    "url": f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_no_dash}/{doc}",
                }
            )
            if len(items) >= limit:
                break

        return {
            "ticker": ticker.upper(),
            "cik": cik,
            "company_name": title,
            "sic": sub.get("sic"),
            "sic_description": sub.get("sicDescription"),
            "fiscal_year_end": sub.get("fiscalYearEnd"),
            "filings": items,
        }

    def download_filing_text(self, url: str, out_path: Path, max_chars: int = 350_000) -> Path:
        raw_html = self._get_text(url)
        soup = BeautifulSoup(raw_html, "lxml")
        for tag in soup(["script", "style", "ix:header"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
        compact = "\n".join(ln for ln in lines if ln)
        if len(compact) > max_chars:
            compact = compact[:max_chars] + "\n\n[TRUNCATED AT MAX_CHARS LIMIT]"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(compact, encoding="utf-8")
        return out_path

    def extract_annual_financials(self, ticker: str, years: int = 5) -> dict[str, Any]:
        cik, title = self.resolve_cik(ticker)
        facts_json = self._get_json(
            f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
            cache_name=f"companyfacts_{cik}.json",
            ttl_hours=24,
        )
        taxonomies = facts_json.get("facts", {})

        def _collect_concept_series(concepts: list[str], is_flow: bool) -> dict[int, float]:
            """Merge across concept aliases preferring higher-priority tags per year."""
            merged: dict[int, tuple[int, str, float]] = {}  # year -> (priority_idx, filed_date, val)
            for prio, concept in enumerate(concepts):
                node = None
                for tax_name in ("us-gaap", "ifrs-full", "dei"):
                    if concept in taxonomies.get(tax_name, {}):
                        node = taxonomies[tax_name][concept]
                        break
                if not node:
                    continue

                units_dict = node.get("units", {})
                # Prefer USD or shares
                unit_key = next(
                    (u for u in ("USD", "shares") if u in units_dict),
                    next(iter(units_dict.keys()), None),
                )
                if not unit_key:
                    continue

                for obs in units_dict[unit_key]:
                    form = str(obs.get("form", "")).upper()
                    if form not in ANNUAL_FORMS:
                        continue
                    end_str = obs.get("end")
                    val = obs.get("val")
                    if not end_str or val is None:
                        continue
                    if is_flow:
                        start_str = obs.get("start")
                        if not start_str:
                            continue
                        try:
                            d0 = datetime.strptime(start_str, "%Y-%m-%d")
                            d1 = datetime.strptime(end_str, "%Y-%m-%d")
                        except ValueError:
                            continue
                        days = (d1 - d0).days
                        if not (330 <= days <= 385):
                            continue
                    try:
                        end_dt = datetime.strptime(end_str, "%Y-%m-%d")
                    except ValueError:
                        continue
                    # Map fiscal year by end_dt year (if end is early Jan, belongs to prior FY)
                    fy = end_dt.year - 1 if (end_dt.month == 1 and end_dt.day <= 15) else end_dt.year
                    filed = str(obs.get("filed", ""))
                    prev = merged.get(fy)
                    if prev is None:
                        merged[fy] = (prio, filed, float(val))
                    else:
                        prev_prio, prev_filed, _ = prev
                        if prio < prev_prio or (prio == prev_prio and filed >= prev_filed):
                            merged[fy] = (prio, filed, float(val))

            return {yr: v[2] for yr, v in merged.items()}

        raw_series: dict[str, dict[int, float]] = {}
        for field, concepts in FLOW_CONCEPTS.items():
            raw_series[field] = _collect_concept_series(concepts, is_flow=True)
        for field, concepts in INSTANT_CONCEPTS.items():
            raw_series[field] = _collect_concept_series(concepts, is_flow=False)

        anchor_years = sorted(
            set(raw_series["revenue"].keys())
            | set(raw_series["net_income"].keys())
            | set(raw_series["total_assets"].keys())
        )
        selected_years = anchor_years[-years:] if len(anchor_years) > years else anchor_years

        annual_table: list[dict[str, Any]] = []
        for yr in selected_years:
            row: dict[str, Any] = {"fiscal_year": yr}
            for k, s in raw_series.items():
                row[k] = s.get(yr)

            rev = row.get("revenue")
            gp = row.get("gross_profit")
            cor = row.get("cost_of_revenue")
            if gp is None and rev is not None and cor is not None:
                row["gross_profit"] = rev - cor
                gp = row["gross_profit"]

            opinc = row.get("operating_income")
            da = row.get("da") or 0.0
            ebitda = (opinc + da) if opinc is not None else None
            row["ebitda_approx"] = ebitda

            ocf = row.get("operating_cash_flow")
            capex = abs(row["capex"]) if row.get("capex") is not None else 0.0
            sbc = row.get("sbc") or 0.0
            fcf = (ocf - capex) if ocf is not None else None
            fcf_ex_sbc = (fcf - sbc) if fcf is not None else None
            row["fcf"] = fcf
            row["fcf_ex_sbc"] = fcf_ex_sbc

            cash = (row.get("cash_and_equivalents") or 0.0) + (
                row.get("short_term_investments") or 0.0
            )
            st_debt = row.get("short_term_debt") or 0.0
            lt_debt = row.get("long_term_debt") or 0.0
            total_debt = st_debt + lt_debt
            net_debt = total_debt - cash
            row["total_cash"] = cash
            row["total_debt"] = total_debt
            row["net_debt"] = net_debt

            pretax = row.get("pretax_income")
            tax = row.get("income_tax")
            eff_tax = (
                max(0.0, min(0.45, tax / pretax))
                if (pretax and pretax > 0 and tax is not None)
                else 0.21
            )
            row["effective_tax_rate"] = round(eff_tax, 4)

            eq = row.get("stockholders_equity")
            invested_cap = (eq + total_debt - cash) if eq is not None else None
            nopat = (opinc * (1.0 - eff_tax)) if opinc is not None else None
            roic = (
                round(nopat / invested_cap, 4)
                if (nopat is not None and invested_cap and invested_cap > 0)
                else None
            )
            row["invested_capital"] = invested_cap
            row["nopat"] = nopat
            row["roic"] = roic

            ni = row.get("net_income")
            row["gross_margin"] = round(gp / rev, 4) if (gp is not None and rev) else None
            row["operating_margin"] = round(opinc / rev, 4) if (opinc is not None and rev) else None
            row["net_margin"] = round(ni / rev, 4) if (ni is not None and rev) else None
            row["fcf_margin"] = round(fcf / rev, 4) if (fcf is not None and rev) else None
            row["sbc_pct_revenue"] = round(sbc / rev, 4) if rev else None
            row["cash_conversion_ocf_ni"] = (
                round(ocf / ni, 4) if (ocf is not None and ni and ni > 0) else None
            )
            row["net_debt_to_ebitda"] = (
                round(net_debt / ebitda, 2) if (ebitda and ebitda > 0) else None
            )
            row["diluted_shares"] = row.get("diluted_shares_flow") or row.get("common_shares_out")
            annual_table.append(row)

        # Compute multi-year CAGRs where available
        cagrs: dict[str, float | None] = {}
        if len(annual_table) >= 2:
            span = annual_table[-1]["fiscal_year"] - annual_table[0]["fiscal_year"]
            if span > 0:
                for metric in ("revenue", "operating_income", "net_income", "fcf", "diluted_shares"):
                    v0 = annual_table[0].get(metric)
                    v1 = annual_table[-1].get(metric)
                    if v0 and v1 and v0 > 0 and v1 > 0:
                        cagrs[f"{metric}_cagr_{span}y"] = round((v1 / v0) ** (1.0 / span) - 1.0, 4)
                    else:
                        cagrs[f"{metric}_cagr_{span}y"] = None

        return {
            "ticker": ticker.upper(),
            "cik": cik,
            "company_name": title,
            "years_extracted": [r["fiscal_year"] for r in annual_table],
            "cagrs": cagrs,
            "annual_financials": annual_table,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch SEC EDGAR filings and normalized XBRL facts.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_facts = sub.add_parser("facts", help="Extract normalized multi-year annual financials")
    p_facts.add_argument("ticker", help="Stock ticker (e.g. AAPL, MSFT, TSM)")
    p_facts.add_argument("--years", type=int, default=5, help="Number of fiscal years")
    p_facts.add_argument("--out", help="Output JSON file path")

    p_filings = sub.add_parser("filings", help="List and optionally download recent SEC filings")
    p_filings.add_argument("ticker", help="Stock ticker")
    p_filings.add_argument("--forms", default="10-K,20-F,10-Q,8-K", help="Comma-separated forms")
    p_filings.add_argument("--limit", type=int, default=10, help="Max filings to return")
    p_filings.add_argument(
        "--download-latest",
        type=int,
        default=0,
        help="Download text of the N most recent matching filings into --out-dir",
    )
    p_filings.add_argument("--out-dir", help="Directory for downloaded filings and metadata JSON")

    args = parser.parse_args()
    client = EdgarClient()

    try:
        if args.cmd == "facts":
            res = client.extract_annual_financials(args.ticker, years=args.years)
            if args.out:
                out_p = Path(args.out)
                out_p.parent.mkdir(parents=True, exist_ok=True)
                out_p.write_text(json.dumps(res, indent=2), encoding="utf-8")
                print(f"Saved {len(res['annual_financials'])} years of EDGAR XBRL facts to {out_p}")
            else:
                print(json.dumps(res, indent=2))

        elif args.cmd == "filings":
            forms = [f.strip() for f in args.forms.split(",") if f.strip()]
            res = client.list_filings(args.ticker, forms=forms, limit=args.limit)
            if args.download_latest > 0:
                base_dir = Path(args.out_dir or f"memory/{args.ticker.upper()}/sources")
                for item in res["filings"][: args.download_latest]:
                    safe_form = item["form"].replace("/", "-")
                    fname = f"{args.ticker.upper()}_{safe_form}_{item['filing_date']}.txt"
                    saved = client.download_filing_text(item["url"], base_dir / fname)
                    item["local_text_path"] = str(saved)
            if args.out_dir:
                meta_path = Path(args.out_dir) / f"{args.ticker.upper()}_filings_index.json"
                meta_path.parent.mkdir(parents=True, exist_ok=True)
                meta_path.write_text(json.dumps(res, indent=2), encoding="utf-8")
                print(f"Saved filings index ({len(res['filings'])} items) to {meta_path}")
            else:
                print(json.dumps(res, indent=2))
    except Exception as exc:
        print(f"EDGAR error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

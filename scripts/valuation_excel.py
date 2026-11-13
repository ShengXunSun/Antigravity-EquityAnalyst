#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "openpyxl>=3.1.5",
# ]
# ///
"""Build a 100% live-formula institutional Excel valuation workbook (.xlsx) + summary JSON."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# Styling constants (Institutional Wall Street convention: Blue=Input, Black=Formula, Green=Cross-Sheet)
FONT_FAMILY = "Calibri"
FONT_TITLE = Font(name=FONT_FAMILY, size=14, bold=True, color="FFFFFF")
FONT_SECTION = Font(name=FONT_FAMILY, size=11, bold=True, color="FFFFFF")
FONT_TBL_HDR = Font(name=FONT_FAMILY, size=10, bold=True, color="1B365D")
FONT_INPUT = Font(name=FONT_FAMILY, size=10, bold=False, color="0000FF")
FONT_INPUT_BOLD = Font(name=FONT_FAMILY, size=10, bold=True, color="0000FF")
FONT_FORMULA = Font(name=FONT_FAMILY, size=10, bold=False, color="000000")
FONT_FORMULA_BOLD = Font(name=FONT_FAMILY, size=10, bold=True, color="000000")
FONT_LINK = Font(name=FONT_FAMILY, size=10, bold=False, color="008000")
FONT_LINK_BOLD = Font(name=FONT_FAMILY, size=10, bold=True, color="008000")
FONT_NOTE = Font(name=FONT_FAMILY, size=9, italic=True, color="4A5568")

FILL_NAVY = PatternFill("solid", fgColor="1B365D")
FILL_SLATE = PatternFill("solid", fgColor="2C5282")
FILL_SUBHDR = PatternFill("solid", fgColor="D9E1F2")
FILL_INPUT = PatternFill("solid", fgColor="FFFDF0")
FILL_TOTAL = PatternFill("solid", fgColor="EDF2F7")
FILL_ACCENT = PatternFill("solid", fgColor="E6FFFA")

THIN_SIDE = Side(border_style="thin", color="CBD5E0")
MED_NAVY = Side(border_style="medium", color="1B365D")
DOUBLE_BOTTOM = Side(border_style="double", color="1B365D")

BORDER_DATA = Border(left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE, bottom=THIN_SIDE)
BORDER_TOTAL = Border(top=THIN_SIDE, bottom=DOUBLE_BOTTOM)
BORDER_HDR = Border(top=MED_NAVY, bottom=MED_NAVY, left=THIN_SIDE, right=THIN_SIDE)

FMT_CURR = "$#,##0.00;($#,##0.00);\"-\""
FMT_INT_M = "$#,##0;($#,##0);\"-\""
FMT_DEC_M = "$#,##0.0;($#,##0.0);\"-\""
FMT_SHARES = "#,##0.0"
FMT_PCT = "0.0%"
FMT_PCT2 = "0.00%"
FMT_MULT = "0.0\"x\""

EXCEL_ERROR_TOKENS = ("#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#N/A", "#NUM!")

KEY_DRIVERS = ("revenue_growth", "ebit_margin", "capex_pct_rev", "premium_discount_pct")
STRUCTURAL_DRIVERS = ("tax_rate", "da_pct_rev", "nwc_pct_delta_rev", "sbc_pct_rev")
TRACKED_ASSUMPTION_DRIVERS = KEY_DRIVERS + STRUCTURAL_DRIVERS

SAMPLE_SPEC: dict[str, Any] = {
    "meta": {
        "ticker": "MSFT",
        "company_name": "Microsoft Corporation",
        "sector": "Information Technology",
        "industry": "Systems Software",
        "model_type": "standard_dcf",
        "valuation_date": "2026-11-13",
        "currency": "USD",
        "units_label": "$ in Millions (except per-share data)",
        "current_price": 425.00,
        "diluted_shares_m": 7430.0,
        "cash_and_investments_m": 78000.0,
        "total_debt_m": 49000.0,
        "preferred_stock_m": 0.0,
        "minority_interest_m": 0.0,
        "ips_buy_upside_hurdle": 0.15,
        "ips_sell_upside_hurdle": -0.05,
        "blend_weights": {
            "dcf_perpetuity": 0.40,
            "dcf_exit_multiple": 0.25,
            "relative_comps": 0.35,
        },
    },
    "thesis_pillars": [
        {
            "id": "T1",
            "title": "Enterprise Cloud & Copilot Seat Monetization",
            "summary": "Commercial cloud RPO and Copilot seat attach sustain low-teens top-line compounding and high-margin software mix.",
            "impacted_drivers": ["revenue_growth", "ebit_margin", "premium_discount_pct"],
            "model_impact": "Drives 5Y Base revenue growth from 14.5% (FY26E) to 10.5% (FY30E) and expands EBIT margin +180 bps (45.0% FY25A to 46.8% FY30E); justifies +10.0% peer EV/EBITDA premium.",
            "bull_bear_flex": "Bull: faster Copilot attach lifts FY26E-30E growth to 16.5%->12.0% and FY30E margin to 49.0%; Bear: seat digestion slows growth to 11.0%->7.5% and compresses margin to 42.5%.",
        },
        {
            "id": "T2",
            "title": "Front-Loaded AI Datacenter CapEx Tapering to Steady State",
            "summary": "Peak GPU/datacenter additions in FY26E-FY27E taper toward normalized utilization and lower reinvestment intensity by Year 5.",
            "impacted_drivers": ["capex_pct_rev", "da_pct_rev"],
            "model_impact": "Models CapEx at 18.5% of revenue in FY26E tapering to 13.5% in FY30E, while server D&A peaks at 10.5% in FY27E-FY28E before normalizing to 10.0%.",
            "bull_bear_flex": "Bull: higher cluster utilization tapers FY30E CapEx to 12.5%; Bear: prolonged GPU refresh keeps FY30E CapEx at 15.5%.",
        },
    ],
    "assumption_basis": {
        "revenue_growth": {
            "basis_type": "thesis",
            "thesis_ids": ["T1"],
            "historical_anchor": "FY23A-FY25A Rev CAGR 14.3% (FY25A +13.0%)",
            "rationale": "T1 (Azure AI backlog + Copilot seat monetization) sustains 14.5%->10.5% 5Y Base compounding.",
        },
        "ebit_margin": {
            "basis_type": "thesis",
            "thesis_ids": ["T1"],
            "historical_anchor": "FY23A-FY25A EBIT margin expanded 41.8% -> 45.0%",
            "rationale": "T1 commercial cloud operating leverage more than offsets GPU depreciation, lifting EBIT margin +180 bps to 46.8% by FY30E.",
        },
        "capex_pct_rev": {
            "basis_type": "thesis",
            "thesis_ids": ["T2"],
            "historical_anchor": "FY23A-FY25A CapEx rose from 13.3% to 19.1% of revenue",
            "rationale": "T2 models front-loaded AI datacenter buildout (18.5% in FY26E) tapering to normalized 13.5% terminal run-rate in FY30E.",
        },
        "premium_discount_pct": {
            "basis_type": "thesis",
            "thesis_ids": ["T1"],
            "historical_anchor": "Mega-cap software/cloud peer median EV/EBITDA 18.45x",
            "rationale": "T1 enterprise seat lock-in and >30% ROIC warrant a +10.0% quality premium over peer median EV/EBITDA.",
        },
        "tax_rate": {
            "basis_type": "historical_or_market",
            "thesis_ids": [],
            "historical_anchor": "FY23A-FY25A normalized effective tax rate ~19.0% (10-K)",
            "rationale": "Held at 19.0% historical statutory/foreign mix anchor; no tax-specific thesis override.",
        },
        "da_pct_rev": {
            "basis_type": "thesis",
            "thesis_ids": ["T2"],
            "historical_anchor": "FY23A-FY25A D&A rose from 6.5% to 9.9% of revenue",
            "rationale": "T2 datacenter CapEx wave lifts server D&A to 10.5% in FY27E-FY28E before easing to 10.0% in FY30E.",
        },
        "nwc_pct_delta_rev": {
            "basis_type": "historical_or_market",
            "thesis_ids": [],
            "historical_anchor": "FY23A-FY25A unearned enterprise billings generated -$1.8B avg NWC cash inflow",
            "rationale": "Anchored to historical commercial cloud deferred-revenue working capital profile (-2.0% to -1.0% of incremental revenue).",
        },
        "sbc_pct_rev": {
            "basis_type": "historical_or_market",
            "thesis_ids": [],
            "historical_anchor": "FY23A-FY25A SBC declined from 4.5% to 4.2% of revenue",
            "rationale": "Anchored to historical engineering dilution discipline tapering gradually from 4.0% to 3.6% of revenue.",
        },
    },
    "wacc_inputs": {
        "risk_free_rate": 0.042,
        "equity_risk_premium": 0.048,
        "beta": 0.95,
        "specific_risk_premium": 0.0,
        "pretax_cost_of_debt": 0.046,
        "marginal_tax_rate": 0.19,
        "terminal_growth_rate": 0.032,
        "exit_multiple": 21.0,
        "rationale": "10Y US Treasury 4.2%, ERP 4.8%, levered beta 0.95; terminal growth 3.2% reflects durable enterprise cloud pricing power.",
    },
    "historicals": [
        {
            "year": 2023,
            "revenue": 211915.0,
            "ebit": 88523.0,
            "da": 13861.0,
            "capex": 28107.0,
            "change_in_nwc": -1500.0,
            "sbc": 9611.0,
        },
        {
            "year": 2024,
            "revenue": 245122.0,
            "ebit": 109433.0,
            "da": 22287.0,
            "capex": 44477.0,
            "change_in_nwc": -2100.0,
            "sbc": 10734.0,
        },
        {
            "year": 2025,
            "revenue": 277000.0,
            "ebit": 124650.0,
            "da": 27500.0,
            "capex": 53000.0,
            "change_in_nwc": -1800.0,
            "sbc": 11600.0,
        },
    ],
    "forecast": {
        "years": [2026, 2027, 2028, 2029, 2030],
        "active_scenario": 1,
        "scenarios": {
            "base": {
                "revenue_growth": [0.145, 0.135, 0.125, 0.115, 0.105],
                "ebit_margin": [0.452, 0.458, 0.462, 0.465, 0.468],
                "tax_rate": [0.190, 0.190, 0.190, 0.190, 0.190],
                "da_pct_rev": [0.102, 0.105, 0.105, 0.102, 0.100],
                "capex_pct_rev": [0.185, 0.175, 0.160, 0.145, 0.135],
                "nwc_pct_delta_rev": [-0.020, -0.020, -0.015, -0.015, -0.010],
                "sbc_pct_rev": [0.040, 0.039, 0.038, 0.037, 0.036],
            },
            "bull": {
                "revenue_growth": [0.165, 0.160, 0.150, 0.135, 0.120],
                "ebit_margin": [0.460, 0.470, 0.478, 0.485, 0.490],
                "tax_rate": [0.190, 0.190, 0.190, 0.190, 0.190],
                "da_pct_rev": [0.102, 0.105, 0.104, 0.100, 0.098],
                "capex_pct_rev": [0.180, 0.165, 0.150, 0.135, 0.125],
                "nwc_pct_delta_rev": [-0.025, -0.020, -0.020, -0.015, -0.015],
                "sbc_pct_rev": [0.039, 0.038, 0.036, 0.035, 0.034],
            },
            "bear": {
                "revenue_growth": [0.110, 0.100, 0.090, 0.080, 0.075],
                "ebit_margin": [0.435, 0.430, 0.428, 0.425, 0.425],
                "tax_rate": [0.200, 0.200, 0.200, 0.200, 0.200],
                "da_pct_rev": [0.105, 0.108, 0.108, 0.105, 0.105],
                "capex_pct_rev": [0.195, 0.185, 0.175, 0.165, 0.155],
                "nwc_pct_delta_rev": [-0.010, -0.010, -0.005, -0.005, 0.000],
                "sbc_pct_rev": [0.043, 0.042, 0.041, 0.040, 0.040],
            },
        },
        "driver_rationales": {
            "revenue_growth": "Azure AI workload monetization + Copilot seat adoption sustains low-to-mid-teens top-line growth before gradual scale normalization.",
            "ebit_margin": "Gross margin pressure from AI GPU depreciation is offset by operating leverage in commercial cloud and disciplined opex headcount growth.",
            "tax_rate": "Aligned with 3-year normalized effective tax rate per 10-K.",
            "da_pct_rev": "Elevated server/datacenter depreciation cycle peaking in FY27-28.",
            "capex_pct_rev": "Front-loaded AI infrastructure buildout tapering from 18.5% toward 13.5% of revenue as utilization scales.",
            "nwc_pct_delta_rev": "Unearned commercial cloud billings generate modest negative working capital cash inflow.",
            "sbc_pct_rev": "Gradual dilution discipline consistent with historical downward SBC/revenue trend.",
        },
    },
    "relative_valuation": {
        "primary_metric": "ev_to_ebitda",
        "company_forward_metric_m": 168000.0,
        "premium_discount_pct": 0.10,
        "premium_discount_rationale": "+10% quality premium to mega-cap software/cloud peer median warranted by superior enterprise seat lock-in and >30% ROIC.",
        "peers": [
            {
                "ticker": "GOOGL",
                "name": "Alphabet Inc.",
                "market_cap_m": 2250000.0,
                "ev_m": 2160000.0,
                "rev_growth": 0.125,
                "ebitda_margin": 0.365,
                "roe": 0.310,
                "forward_pe": 22.5,
                "ev_to_ebitda": 15.8,
                "ev_to_revenue": 6.2,
                "fcf_yield": 0.034,
            },
            {
                "ticker": "AMZN",
                "name": "Amazon.com Inc.",
                "market_cap_m": 2180000.0,
                "ev_m": 2210000.0,
                "rev_growth": 0.112,
                "ebitda_margin": 0.215,
                "roe": 0.225,
                "forward_pe": 31.0,
                "ev_to_ebitda": 17.4,
                "ev_to_revenue": 3.5,
                "fcf_yield": 0.026,
            },
            {
                "ticker": "ORCL",
                "name": "Oracle Corp.",
                "market_cap_m": 470000.0,
                "ev_m": 545000.0,
                "rev_growth": 0.095,
                "ebitda_margin": 0.410,
                "roe": 0.520,
                "forward_pe": 25.4,
                "ev_to_ebitda": 20.2,
                "ev_to_revenue": 9.3,
                "fcf_yield": 0.025,
            },
            {
                "ticker": "CRM",
                "name": "Salesforce Inc.",
                "market_cap_m": 310000.0,
                "ev_m": 305000.0,
                "rev_growth": 0.088,
                "ebitda_margin": 0.340,
                "roe": 0.115,
                "forward_pe": 27.2,
                "ev_to_ebitda": 19.5,
                "ev_to_revenue": 7.8,
                "fcf_yield": 0.039,
            },
        ],
    },
}


def _style_banner(ws: Any, title: str, subtitle: str, max_col: int = 10) -> None:
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max_col)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=max_col)
    c1 = ws.cell(1, 1, title)
    c1.font = FONT_TITLE
    c1.fill = FILL_NAVY
    c1.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[1].height = 26

    c2 = ws.cell(2, 1, subtitle)
    c2.font = Font(name=FONT_FAMILY, size=9, italic=True, color="E2E8F0")
    c2.fill = FILL_SLATE
    c2.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[2].height = 18


def _style_section_bar(ws: Any, row: int, text: str, max_col: int = 10) -> None:
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=max_col)
    c = ws.cell(row, 1, text)
    c.font = FONT_SECTION
    c.fill = FILL_NAVY
    c.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[row].height = 21


def _format_basis_tag(basis_entry: dict[str, Any]) -> str:
    if basis_entry.get("basis_type") == "thesis":
        tids = ", ".join(basis_entry.get("thesis_ids", []))
        return f"Thesis: {tids}"
    return "Historical / Market Anchor"


def _validate_spec(spec: dict[str, Any]) -> None:
    fc = spec.get("forecast", {})
    years = fc.get("years", [])
    if len(years) != 5:
        raise ValueError(
            f"DCF model requires a strict 5-year explicit forecast horizon: "
            f"forecast['years'] must contain exactly 5 years (got {len(years)}: {years}). "
            f"Calibrate Year 5 drivers to normalized terminal run-rate margins and reinvestment."
        )
    required_drivers = (
        "revenue_growth",
        "ebit_margin",
        "tax_rate",
        "da_pct_rev",
        "capex_pct_rev",
        "nwc_pct_delta_rev",
        "sbc_pct_rev",
    )
    for sc_name in ("base", "bull", "bear"):
        sc = fc.get("scenarios", {}).get(sc_name, {})
        for drv in required_drivers:
            vals = sc.get(drv, [])
            if len(vals) != 5:
                raise ValueError(
                    f"forecast.scenarios.{sc_name}.{drv} must contain exactly 5 annual values (got {len(vals)})."
                )

    # Validate Variant Thesis Pillars (T1..Tn)
    pillars = spec.get("thesis_pillars", [])
    if not isinstance(pillars, list) or not pillars:
        raise ValueError(
            "valuation_spec.json must define a non-empty 'thesis_pillars' list (T1..Tn) linking the investment thesis to model drivers."
        )

    pillar_map: dict[str, dict[str, Any]] = {}
    for p in pillars:
        pid = str(p.get("id", "")).strip()
        if not re.fullmatch(r"T\d+", pid):
            raise ValueError(f"Thesis pillar id '{pid}' must match 'T1', 'T2', ... format.")
        if pid in pillar_map:
            raise ValueError(f"Duplicate thesis pillar id '{pid}' in thesis_pillars.")
        for req_f in ("title", "model_impact", "bull_bear_flex"):
            if not str(p.get(req_f, "")).strip():
                raise ValueError(f"Thesis pillar '{pid}' is missing non-empty '{req_f}'.")
        imp = p.get("impacted_drivers", [])
        if not isinstance(imp, list) or not imp:
            raise ValueError(f"Thesis pillar '{pid}' must list at least one driver in 'impacted_drivers'.")
        for drv in imp:
            if drv not in TRACKED_ASSUMPTION_DRIVERS:
                raise ValueError(
                    f"Thesis pillar '{pid}' references unknown driver '{drv}'. Allowed: {TRACKED_ASSUMPTION_DRIVERS}"
                )
        pillar_map[pid] = p

    # Validate Two-Tier Assumption Basis & Bidirectional Integrity
    ab = spec.get("assumption_basis", {})
    if not isinstance(ab, dict):
        raise ValueError("valuation_spec.json must include an 'assumption_basis' object covering all model drivers.")

    thesis_key_driver_count = 0
    for drv in TRACKED_ASSUMPTION_DRIVERS:
        if drv not in ab or not isinstance(ab[drv], dict):
            raise ValueError(
                f"assumption_basis is missing required driver '{drv}'. Every driver must declare 'basis_type', 'thesis_ids', 'historical_anchor', and 'rationale'."
            )
        entry = ab[drv]
        btype = entry.get("basis_type")
        if btype not in ("thesis", "historical_or_market"):
            raise ValueError(
                f"assumption_basis.{drv}.basis_type must be 'thesis' or 'historical_or_market' (got {btype!r})."
            )
        tids = entry.get("thesis_ids", [])
        if not isinstance(tids, list):
            raise ValueError(f"assumption_basis.{drv}.thesis_ids must be a list.")
        if not str(entry.get("historical_anchor", "")).strip():
            raise ValueError(f"assumption_basis.{drv}.historical_anchor must be non-empty.")
        if not str(entry.get("rationale", "")).strip():
            raise ValueError(f"assumption_basis.{drv}.rationale must be non-empty.")

        if btype == "thesis":
            if not tids:
                raise ValueError(
                    f"assumption_basis.{drv} has basis_type='thesis' and must list at least one Thesis Pillar ID in thesis_ids."
                )
            for tid in tids:
                if tid not in pillar_map:
                    raise ValueError(f"assumption_basis.{drv} references undefined thesis_id '{tid}'.")
                if drv not in pillar_map[tid]["impacted_drivers"]:
                    raise ValueError(
                        f"Bidirectional mismatch: assumption_basis.{drv} links to '{tid}', "
                        f"so thesis_pillars['{tid}'].impacted_drivers must also include '{drv}'."
                    )
            if drv in KEY_DRIVERS:
                thesis_key_driver_count += 1
        else:
            if tids:
                raise ValueError(
                    f"assumption_basis.{drv} has basis_type='historical_or_market', so thesis_ids must be empty []."
                )

    for pid, p in pillar_map.items():
        for drv in p["impacted_drivers"]:
            if ab[drv].get("basis_type") != "thesis" or pid not in ab[drv].get("thesis_ids", []):
                raise ValueError(
                    f"Bidirectional mismatch: thesis_pillars['{pid}'] lists '{drv}' in impacted_drivers, "
                    f"so assumption_basis.{drv} must set basis_type='thesis' and include '{pid}' in thesis_ids."
                )

    if thesis_key_driver_count == 0:
        raise ValueError(
            f"At least one Key Driver {KEY_DRIVERS} must be thesis-driven (basis_type='thesis')."
        )


def _compute_python_shadow(spec: dict[str, Any]) -> dict[str, Any]:
    """Deterministically mirror Excel math so report-to-model audit has exact reference values."""
    _validate_spec(spec)
    meta = spec["meta"]
    model_type = meta.get("model_type", "standard_dcf")
    wi = spec["wacc_inputs"]
    fc = spec["forecast"]
    years = fc["years"]
    n_yr = len(years)
    hist = spec["historicals"]
    last_rev = float(hist[-1]["revenue"])

    ke = float(wi["risk_free_rate"]) + float(wi["beta"]) * float(wi["equity_risk_premium"]) + float(
        wi.get("specific_risk_premium", 0.0)
    )
    mcap = float(meta["current_price"]) * float(meta["diluted_shares_m"])
    debt = float(meta["total_debt_m"])
    tot_cap = mcap + debt
    kd_after = float(wi["pretax_cost_of_debt"]) * (1.0 - float(wi["marginal_tax_rate"]))

    if model_type == "financials_ddm":
        disc_rate = ke
    else:
        w_e = mcap / tot_cap if tot_cap > 0 else 1.0
        w_d = debt / tot_cap if tot_cap > 0 else 0.0
        disc_rate = w_e * ke + w_d * kd_after

    tg = float(wi["terminal_growth_rate"])
    exit_mult = float(wi["exit_multiple"])
    shares = float(meta["diluted_shares_m"])
    cash = float(meta["cash_and_investments_m"])
    pref = float(meta.get("preferred_stock_m", 0.0))
    mi = float(meta.get("minority_interest_m", 0.0))

    def _eval_case(case_name: str) -> dict[str, Any]:
        sc = fc["scenarios"][case_name]
        rev = last_rev
        cfs: list[float] = []
        ebitdas: list[float] = []
        revs: list[float] = []
        ebits: list[float] = []
        fcfs_ex_sbc: list[float] = []
        for i in range(n_yr):
            prev_r = rev
            rev = prev_r * (1.0 + float(sc["revenue_growth"][i]))
            ebit = rev * float(sc["ebit_margin"][i])
            tax = float(sc["tax_rate"][i])
            nopat = ebit * (1.0 - tax)
            da = rev * float(sc["da_pct_rev"][i])
            capex = rev * float(sc["capex_pct_rev"][i])
            dnwc = (rev - prev_r) * float(sc["nwc_pct_delta_rev"][i])
            sbc = rev * float(sc["sbc_pct_rev"][i])
            ebitda = ebit + da
            if model_type == "financials_ddm":
                # Excess return / distributable equity cash flow proxy (NOPAT less retained capital growth)
                cf = nopat - capex - dnwc
            elif model_type == "reit_affo":
                # AFFO proxy (Operating cash flow after maintenance capex)
                cf = nopat + da - capex - dnwc
            else:
                cf = nopat + da - capex - dnwc
            revs.append(rev)
            ebits.append(ebit)
            ebitdas.append(ebitda)
            cfs.append(cf)
            fcfs_ex_sbc.append(cf - sbc)

        pv_cfs = sum(cfs[i] / ((1.0 + disc_rate) ** (i + 1)) for i in range(n_yr))
        tv_perp = (cfs[-1] * (1.0 + tg)) / (disc_rate - tg)
        pv_tv_perp = tv_perp / ((1.0 + disc_rate) ** n_yr)

        terminal_metric = cfs[-1] if model_type in ("financials_ddm", "reit_affo") else ebitdas[-1]
        tv_mult = terminal_metric * exit_mult
        pv_tv_mult = tv_mult / ((1.0 + disc_rate) ** n_yr)

        if model_type == "financials_ddm":
            eq_perp = pv_cfs + pv_tv_perp
            eq_mult = pv_cfs + pv_tv_mult
            ev_perp = eq_perp
            ev_mult = eq_mult
        else:
            ev_perp = pv_cfs + pv_tv_perp
            ev_mult = pv_cfs + pv_tv_mult
            eq_perp = ev_perp + cash - debt - pref - mi
            eq_mult = ev_mult + cash - debt - pref - mi

        return {
            "revenues": [round(x, 2) for x in revs],
            "ebits": [round(x, 2) for x in ebits],
            "ebitdas": [round(x, 2) for x in ebitdas],
            "cash_flows": [round(x, 2) for x in cfs],
            "fcfs_ex_sbc": [round(x, 2) for x in fcfs_ex_sbc],
            "pv_explicit_cfs": round(pv_cfs, 2),
            "ev_perpetuity": round(ev_perp, 2),
            "ev_exit_multiple": round(ev_mult, 2),
            "equity_perpetuity": round(eq_perp, 2),
            "equity_exit_multiple": round(eq_mult, 2),
            "share_price_perpetuity": round(eq_perp / shares, 2),
            "share_price_exit_multiple": round(eq_mult / shares, 2),
        }

    cases = {c: _eval_case(c) for c in ("base", "bull", "bear")}

    # Relative valuation shadow
    rv = spec["relative_valuation"]
    metric_key = rv["primary_metric"]
    peer_vals = sorted(
        float(p[metric_key]) for p in rv["peers"] if p.get(metric_key) is not None
    )
    n_p = len(peer_vals)
    if n_p == 0:
        raise ValueError(f"No peers have valid values for primary_metric '{metric_key}'")
    median_mult = (
        peer_vals[n_p // 2]
        if n_p % 2 == 1
        else 0.5 * (peer_vals[n_p // 2 - 1] + peer_vals[n_p // 2])
    )
    adj_mult = median_mult * (1.0 + float(rv.get("premium_discount_pct", 0.0)))
    comp_metric_val = float(rv["company_forward_metric_m"])
    if metric_key.startswith("ev_"):
        implied_ev_comps = comp_metric_val * adj_mult
        implied_eq_comps = implied_ev_comps + cash - debt - pref - mi
    else:
        # Equity multiple (forward_pe, price_to_book, p_affo)
        implied_eq_comps = comp_metric_val * adj_mult
    comps_price = round(implied_eq_comps / shares, 2)

    bw = meta["blend_weights"]
    blended_tp = round(
        float(bw["dcf_perpetuity"]) * cases["base"]["share_price_perpetuity"]
        + float(bw["dcf_exit_multiple"]) * cases["base"]["share_price_exit_multiple"]
        + float(bw["relative_comps"]) * comps_price,
        2,
    )
    cur_p = float(meta["current_price"])
    upside = (blended_tp / cur_p) - 1.0
    buy_h = float(meta["ips_buy_upside_hurdle"])
    sell_h = float(meta["ips_sell_upside_hurdle"])
    rating = "BUY" if upside >= buy_h else ("SELL" if upside <= sell_h else "HOLD")

    return {
        "ticker": meta["ticker"],
        "company_name": meta["company_name"],
        "model_type": model_type,
        "valuation_date": meta["valuation_date"],
        "current_price": cur_p,
        "discount_rate_wacc_or_ke": round(disc_rate, 4),
        "cost_of_equity": round(ke, 4),
        "terminal_growth_rate": tg,
        "exit_multiple": exit_mult,
        "blended_target_price": blended_tp,
        "implied_upside_pct": round(upside * 100.0, 2),
        "rating": rating,
        "ips_buy_hurdle_pct": round(buy_h * 100.0, 2),
        "ips_sell_hurdle_pct": round(sell_h * 100.0, 2),
        "relative_valuation": {
            "primary_metric": metric_key,
            "peer_median_multiple": round(median_mult, 2),
            "applied_multiple": round(adj_mult, 2),
            "premium_discount_pct": round(float(rv.get("premium_discount_pct", 0.0)) * 100.0, 2),
            "implied_share_price": comps_price,
        },
        "thesis_pillars": spec["thesis_pillars"],
        "assumption_basis": spec["assumption_basis"],
        "scenarios": cases,
    }


def build_valuation_workbook(spec: dict[str, Any], out_xlsx: Path) -> dict[str, Any]:
    _validate_spec(spec)
    meta = spec["meta"]
    model_type = meta.get("model_type", "standard_dcf")
    wi = spec["wacc_inputs"]
    hist = spec["historicals"]
    fc = spec["forecast"]
    rv = spec["relative_valuation"]
    ab = spec["assumption_basis"]
    pillars = spec["thesis_pillars"]

    years_hist = [int(h["year"]) for h in hist]
    years_fc = [int(y) for y in fc["years"]]
    n_hist = len(years_hist)
    n_fc = len(years_fc)

    wb = openpyxl.Workbook()
    ws_exec = wb.active
    ws_exec.title = "Executive Summary"
    ws_assump = wb.create_sheet("Assumptions & Scenarios")
    ws_proj = wb.create_sheet("Historical & Forecast")
    ws_dcf = wb.create_sheet("WACC & Intrinsic Value")
    ws_comps = wb.create_sheet("Relative Valuation")

    for ws in wb.worksheets:
        ws.views.sheetView[0].showGridLines = True

    subtitle = (
        f"{meta['company_name']} ({meta['ticker']}) | Model: {model_type} | "
        f"Date: {meta['valuation_date']} | {meta['units_label']}"
    )

    # =========================================================================
    # TAB 2: ASSUMPTIONS & SCENARIOS
    # =========================================================================
    max_c_assump = 2 + n_fc + 2
    _style_banner(ws_assump, f"{meta['ticker']} - Forecast Drivers, Thesis Linkage & Scenario Assumptions", subtitle, max_c_assump)
    ws_assump.cell(4, 1, "Active Scenario Selector (1=Base, 2=Bull, 3=Bear)").font = FONT_FORMULA_BOLD
    c_sel = ws_assump.cell(4, 2, int(fc.get("active_scenario", 1)))
    c_sel.font = FONT_INPUT_BOLD
    c_sel.fill = FILL_INPUT
    c_sel.border = BORDER_DATA
    c_sel.alignment = Alignment(horizontal="center")

    c_sel_lbl = ws_assump.cell(4, 3, '=CHOOSE(B4,"Base Case","Bull Case","Bear Case")')
    c_sel_lbl.font = FONT_FORMULA_BOLD
    c_sel_lbl.fill = FILL_ACCENT
    c_sel_lbl.alignment = Alignment(horizontal="center")

    driver_defs = [
        ("revenue_growth", "Revenue Growth (%)", FMT_PCT),
        ("ebit_margin", "Operating / EBIT Margin (%)", FMT_PCT),
        ("tax_rate", "Effective Tax Rate (%)", FMT_PCT),
        ("da_pct_rev", "D&A (% of Revenue)", FMT_PCT),
        ("capex_pct_rev", "CapEx (% of Revenue)", FMT_PCT),
        ("nwc_pct_delta_rev", "Change in NWC (% of Incremental Rev)", FMT_PCT),
        ("sbc_pct_rev", "Stock-Based Comp (% of Revenue)", FMT_PCT),
    ]

    # Active block (rows 6..14) using =CHOOSE($B$4, Base, Bull, Bear) + Two-Tier Thesis Tag
    _style_section_bar(ws_assump, 6, "Active 5-Year Forecast Drivers & Two-Tier Assumption Basis (Selector in B4)", max_c_assump)
    ws_assump.cell(7, 1, "Driver").font = FONT_TBL_HDR
    ws_assump.cell(7, 2, "Basis / Thesis Tag").font = FONT_TBL_HDR
    ws_assump.cell(7, 1).fill = FILL_SUBHDR
    ws_assump.cell(7, 2).fill = FILL_SUBHDR
    for j, yr in enumerate(years_fc):
        cell = ws_assump.cell(7, 3 + j, f"{yr}E")
        cell.font = FONT_TBL_HDR
        cell.fill = FILL_SUBHDR
        cell.alignment = Alignment(horizontal="right")
    ws_assump.cell(7, 3 + n_fc, "Historical / Market Anchor").font = FONT_TBL_HDR
    ws_assump.cell(7, 3 + n_fc).fill = FILL_SUBHDR
    ws_assump.cell(7, 4 + n_fc, "Thesis / Historical Rationale").font = FONT_TBL_HDR
    ws_assump.cell(7, 4 + n_fc).fill = FILL_SUBHDR

    # Scenario input blocks below Active block
    scenario_row_map: dict[str, dict[str, int]] = {"active": {}, "base": {}, "bull": {}, "bear": {}}
    cur_r = 16
    for sc_key, sc_title in (("base", "Scenario 1: Base Case Inputs"), ("bull", "Scenario 2: Bull Case Inputs"), ("bear", "Scenario 3: Bear Case Inputs")):
        _style_section_bar(ws_assump, cur_r, sc_title, max_c_assump)
        cur_r += 1
        ws_assump.cell(cur_r, 1, "Driver").font = FONT_TBL_HDR
        ws_assump.cell(cur_r, 2, "Scenario").font = FONT_TBL_HDR
        for j, yr in enumerate(years_fc):
            hcell = ws_assump.cell(cur_r, 3 + j, f"{yr}E")
            hcell.font = FONT_TBL_HDR
            hcell.fill = FILL_SUBHDR
            hcell.alignment = Alignment(horizontal="right")
        cur_r += 1
        for d_key, d_label, d_fmt in driver_defs:
            scenario_row_map[sc_key][d_key] = cur_r
            ws_assump.cell(cur_r, 1, d_label).font = FONT_FORMULA
            ws_assump.cell(cur_r, 2, sc_key.upper()).font = FONT_NOTE
            vals = fc["scenarios"][sc_key][d_key]
            for j in range(n_fc):
                ic = ws_assump.cell(cur_r, 3 + j, float(vals[j]))
                ic.font = FONT_INPUT
                ic.fill = FILL_INPUT
                ic.number_format = d_fmt
                ic.border = BORDER_DATA
            cur_r += 1
        cur_r += 1

    # Populate Active rows with =CHOOSE($B$4, BaseCell, BullCell, BearCell) + Basis Tag
    for idx, (d_key, d_label, d_fmt) in enumerate(driver_defs):
        r_act = 8 + idx
        scenario_row_map["active"][d_key] = r_act
        ws_assump.cell(r_act, 1, d_label).font = FONT_FORMULA_BOLD
        b_entry = ab[d_key]
        b_tag = _format_basis_tag(b_entry)
        b_cell = ws_assump.cell(r_act, 2, b_tag)
        if b_entry.get("basis_type") == "thesis":
            b_cell.font = FONT_FORMULA_BOLD
            b_cell.fill = FILL_ACCENT
        else:
            b_cell.font = FONT_NOTE
            b_cell.fill = FILL_TOTAL
        b_cell.border = BORDER_DATA
        for j in range(n_fc):
            col_ltr = get_column_letter(3 + j)
            r_b = scenario_row_map["base"][d_key]
            r_u = scenario_row_map["bull"][d_key]
            r_r = scenario_row_map["bear"][d_key]
            f_cell = ws_assump.cell(
                r_act, 3 + j, f"=CHOOSE($B$4,{col_ltr}{r_b},{col_ltr}{r_u},{col_ltr}{r_r})"
            )
            f_cell.font = FONT_FORMULA
            f_cell.number_format = d_fmt
            f_cell.border = BORDER_DATA
        anch_cell = ws_assump.cell(r_act, 3 + n_fc, b_entry.get("historical_anchor", ""))
        anch_cell.font = FONT_NOTE
        anch_cell.alignment = Alignment(wrap_text=True)
        anch_cell.border = BORDER_DATA
        rat_cell = ws_assump.cell(r_act, 4 + n_fc, b_entry.get("rationale", fc.get("driver_rationales", {}).get(d_key, "")))
        rat_cell.font = FONT_NOTE
        rat_cell.alignment = Alignment(wrap_text=True)
        rat_cell.border = BORDER_DATA

    # Section 4 on Tab 2: Variant Thesis Pillars (T1..Tn) -> Model Impact Map
    _style_section_bar(ws_assump, cur_r, "Variant Thesis Pillars (T1..Tn) -> Model Impact Map", max_c_assump)
    cur_r += 1
    thesis_hdrs = [
        (1, "Pillar ID"),
        (2, "Thesis Title"),
        (3, "Impacted Drivers"),
        (4, "5-Year Base Trajectory Impact"),
        (8, "Bull vs. Bear Scenario Flex"),
    ]
    for c_idx, h_lbl in thesis_hdrs:
        hc = ws_assump.cell(cur_r, c_idx, h_lbl)
        hc.font = FONT_TBL_HDR
        hc.fill = FILL_SUBHDR
        hc.border = BORDER_HDR
    ws_assump.merge_cells(start_row=cur_r, start_column=4, end_row=cur_r, end_column=7)
    ws_assump.merge_cells(start_row=cur_r, start_column=8, end_row=cur_r, end_column=max_c_assump)
    cur_r += 1
    for p in pillars:
        c_id = ws_assump.cell(cur_r, 1, p["id"])
        c_id.font = FONT_FORMULA_BOLD
        c_id.fill = FILL_ACCENT
        c_id.alignment = Alignment(horizontal="center", vertical="top")
        c_id.border = BORDER_DATA

        c_ti = ws_assump.cell(cur_r, 2, p["title"])
        c_ti.font = FONT_FORMULA_BOLD
        c_ti.alignment = Alignment(wrap_text=True, vertical="top")
        c_ti.border = BORDER_DATA

        c_dr = ws_assump.cell(cur_r, 3, ", ".join(p["impacted_drivers"]))
        c_dr.font = FONT_NOTE
        c_dr.alignment = Alignment(wrap_text=True, vertical="top")
        c_dr.border = BORDER_DATA

        ws_assump.merge_cells(start_row=cur_r, start_column=4, end_row=cur_r, end_column=7)
        c_mi = ws_assump.cell(cur_r, 4, p["model_impact"])
        c_mi.font = FONT_FORMULA
        c_mi.alignment = Alignment(wrap_text=True, vertical="top")
        c_mi.border = BORDER_DATA

        ws_assump.merge_cells(start_row=cur_r, start_column=8, end_row=cur_r, end_column=max_c_assump)
        c_fl = ws_assump.cell(cur_r, 8, p["bull_bear_flex"])
        c_fl.font = FONT_NOTE
        c_fl.alignment = Alignment(wrap_text=True, vertical="top")
        c_fl.border = BORDER_DATA
        ws_assump.row_dimensions[cur_r].height = 38
        cur_r += 1

    # =========================================================================
    # TAB 3: HISTORICAL & FORECAST
    # =========================================================================
    tot_cols_proj = 2 + n_hist + n_fc
    _style_banner(ws_proj, f"{meta['ticker']} - Normalized Historicals & Explicit Cash Flow Forecast", subtitle, tot_cols_proj)
    _style_section_bar(ws_proj, 4, "Operating & Unlevered Cash Flow Schedule (Active Scenario)", tot_cols_proj)

    ws_proj.cell(5, 1, "Line Item").font = FONT_TBL_HDR
    ws_proj.cell(5, 2, "Units").font = FONT_TBL_HDR
    for i, yr in enumerate(years_hist):
        c = ws_proj.cell(5, 3 + i, f"{yr}A")
        c.font = FONT_TBL_HDR
        c.fill = FILL_SUBHDR
        c.alignment = Alignment(horizontal="right")
    for j, yr in enumerate(years_fc):
        c = ws_proj.cell(5, 3 + n_hist + j, f"{yr}E")
        c.font = FONT_TBL_HDR
        c.fill = FILL_ACCENT
        c.alignment = Alignment(horizontal="right")

    proj_rows = {
        "rev": 6,
        "rev_g": 7,
        "ebit": 8,
        "ebit_m": 9,
        "tax_rate": 10,
        "nopat": 11,
        "da": 12,
        "ebitda": 13,
        "capex": 14,
        "dnwc": 15,
        "ufcf": 16,
        "sbc": 17,
        "fcf_ex_sbc": 18,
    }
    cf_label = (
        "Distributable Equity Cash Flow"
        if model_type == "financials_ddm"
        else ("Adjusted FFO (AFFO)" if model_type == "reit_affo" else "Unlevered Free Cash Flow (UFCF)")
    )
    row_specs_proj = [
        ("rev", "Revenue", "$M", FMT_INT_M, True),
        ("rev_g", "Revenue Growth (%)", "%", FMT_PCT, False),
        ("ebit", "Operating Income (EBIT)", "$M", FMT_INT_M, False),
        ("ebit_m", "Operating Margin (%)", "%", FMT_PCT, False),
        ("tax_rate", "Effective Tax Rate (%)", "%", FMT_PCT, False),
        ("nopat", "NOPAT / Operating After-Tax Profit", "$M", FMT_INT_M, True),
        ("da", "Depreciation & Amortization (+)", "$M", FMT_INT_M, False),
        ("ebitda", "EBITDA", "$M", FMT_INT_M, True),
        ("capex", "Capital Expenditures (-)", "$M", FMT_INT_M, False),
        ("dnwc", "Change in Net Working Capital (-)", "$M", FMT_INT_M, False),
        ("ufcf", cf_label, "$M", FMT_INT_M, True),
        ("sbc", "Memo: Stock-Based Compensation", "$M", FMT_INT_M, False),
        ("fcf_ex_sbc", "Memo: Cash Flow ex-SBC", "$M", FMT_INT_M, True),
    ]

    for key, lbl, unit, _, is_bold in row_specs_proj:
        r = proj_rows[key]
        c_lbl = ws_proj.cell(r, 1, lbl)
        c_lbl.font = FONT_FORMULA_BOLD if is_bold else FONT_FORMULA
        ws_proj.cell(r, 2, unit).font = FONT_NOTE
        if is_bold:
            c_lbl.fill = FILL_TOTAL

    # Populate Historicals
    for i, h in enumerate(hist):
        col = 3 + i
        cl = get_column_letter(col)
        prev_cl = get_column_letter(col - 1) if i > 0 else None

        for key, h_field in (
            ("rev", "revenue"),
            ("ebit", "ebit"),
            ("da", "da"),
            ("capex", "capex"),
            ("dnwc", "change_in_nwc"),
            ("sbc", "sbc"),
        ):
            c = ws_proj.cell(proj_rows[key], col, float(h.get(h_field, 0.0)))
            c.font = FONT_INPUT
            c.fill = FILL_INPUT
            c.number_format = FMT_INT_M

        c_rg = ws_proj.cell(
            proj_rows["rev_g"],
            col,
            f"=({cl}{proj_rows['rev']}/{prev_cl}{proj_rows['rev']})-1" if prev_cl else 0.0,
        )
        c_rg.font = FONT_FORMULA if prev_cl else FONT_NOTE
        c_rg.number_format = FMT_PCT

        c_em = ws_proj.cell(proj_rows["ebit_m"], col, f"={cl}{proj_rows['ebit']}/{cl}{proj_rows['rev']}")
        c_em.font = FONT_FORMULA
        c_em.number_format = FMT_PCT

        c_tx = ws_proj.cell(proj_rows["tax_rate"], col, float(h.get("tax_rate", wi["marginal_tax_rate"])))
        c_tx.font = FONT_INPUT
        c_tx.fill = FILL_INPUT
        c_tx.number_format = FMT_PCT

        c_np = ws_proj.cell(proj_rows["nopat"], col, f"={cl}{proj_rows['ebit']}*(1-{cl}{proj_rows['tax_rate']})")
        c_np.font = FONT_FORMULA_BOLD
        c_np.number_format = FMT_INT_M

        c_eb = ws_proj.cell(proj_rows["ebitda"], col, f"={cl}{proj_rows['ebit']}+{cl}{proj_rows['da']}")
        c_eb.font = FONT_FORMULA_BOLD
        c_eb.number_format = FMT_INT_M

        ufcf_f = (
            f"={cl}{proj_rows['nopat']}-{cl}{proj_rows['capex']}-{cl}{proj_rows['dnwc']}"
            if model_type == "financials_ddm"
            else f"={cl}{proj_rows['nopat']}+{cl}{proj_rows['da']}-{cl}{proj_rows['capex']}-{cl}{proj_rows['dnwc']}"
        )
        c_uf = ws_proj.cell(proj_rows["ufcf"], col, ufcf_f)
        c_uf.font = FONT_FORMULA_BOLD
        c_uf.fill = FILL_TOTAL
        c_uf.border = BORDER_TOTAL
        c_uf.number_format = FMT_INT_M

        c_xs = ws_proj.cell(proj_rows["fcf_ex_sbc"], col, f"={cl}{proj_rows['ufcf']}-{cl}{proj_rows['sbc']}")
        c_xs.font = FONT_FORMULA_BOLD
        c_xs.number_format = FMT_INT_M

    # Populate Forecast columns linked to 'Assumptions & Scenarios'
    for j in range(n_fc):
        col = 3 + n_hist + j
        cl = get_column_letter(col)
        prev_cl = get_column_letter(col - 1)
        assump_cl = get_column_letter(3 + j)

        c_rg = ws_proj.cell(
            proj_rows["rev_g"],
            col,
            f"='Assumptions & Scenarios'!{assump_cl}{scenario_row_map['active']['revenue_growth']}",
        )
        c_rg.font = FONT_LINK
        c_rg.number_format = FMT_PCT

        c_rv = ws_proj.cell(proj_rows["rev"], col, f"={prev_cl}{proj_rows['rev']}*(1+{cl}{proj_rows['rev_g']})")
        c_rv.font = FONT_FORMULA_BOLD
        c_rv.fill = FILL_TOTAL
        c_rv.number_format = FMT_INT_M

        c_em = ws_proj.cell(
            proj_rows["ebit_m"],
            col,
            f"='Assumptions & Scenarios'!{assump_cl}{scenario_row_map['active']['ebit_margin']}",
        )
        c_em.font = FONT_LINK
        c_em.number_format = FMT_PCT

        c_ebit = ws_proj.cell(proj_rows["ebit"], col, f"={cl}{proj_rows['rev']}*{cl}{proj_rows['ebit_m']}")
        c_ebit.font = FONT_FORMULA
        c_ebit.number_format = FMT_INT_M

        c_tx = ws_proj.cell(
            proj_rows["tax_rate"],
            col,
            f"='Assumptions & Scenarios'!{assump_cl}{scenario_row_map['active']['tax_rate']}",
        )
        c_tx.font = FONT_LINK
        c_tx.number_format = FMT_PCT

        c_np = ws_proj.cell(proj_rows["nopat"], col, f"={cl}{proj_rows['ebit']}*(1-{cl}{proj_rows['tax_rate']})")
        c_np.font = FONT_FORMULA_BOLD
        c_np.fill = FILL_TOTAL
        c_np.number_format = FMT_INT_M

        c_da = ws_proj.cell(
            proj_rows["da"],
            col,
            f"={cl}{proj_rows['rev']}*'Assumptions & Scenarios'!{assump_cl}{scenario_row_map['active']['da_pct_rev']}",
        )
        c_da.font = FONT_LINK
        c_da.number_format = FMT_INT_M

        c_ebitda = ws_proj.cell(proj_rows["ebitda"], col, f"={cl}{proj_rows['ebit']}+{cl}{proj_rows['da']}")
        c_ebitda.font = FONT_FORMULA_BOLD
        c_ebitda.fill = FILL_TOTAL
        c_ebitda.number_format = FMT_INT_M

        c_cx = ws_proj.cell(
            proj_rows["capex"],
            col,
            f"={cl}{proj_rows['rev']}*'Assumptions & Scenarios'!{assump_cl}{scenario_row_map['active']['capex_pct_rev']}",
        )
        c_cx.font = FONT_LINK
        c_cx.number_format = FMT_INT_M

        c_nw = ws_proj.cell(
            proj_rows["dnwc"],
            col,
            f"=({cl}{proj_rows['rev']}-{prev_cl}{proj_rows['rev']})*'Assumptions & Scenarios'!{assump_cl}{scenario_row_map['active']['nwc_pct_delta_rev']}",
        )
        c_nw.font = FONT_LINK
        c_nw.number_format = FMT_INT_M

        ufcf_f = (
            f"={cl}{proj_rows['nopat']}-{cl}{proj_rows['capex']}-{cl}{proj_rows['dnwc']}"
            if model_type == "financials_ddm"
            else f"={cl}{proj_rows['nopat']}+{cl}{proj_rows['da']}-{cl}{proj_rows['capex']}-{cl}{proj_rows['dnwc']}"
        )
        c_uf = ws_proj.cell(proj_rows["ufcf"], col, ufcf_f)
        c_uf.font = FONT_FORMULA_BOLD
        c_uf.fill = FILL_TOTAL
        c_uf.border = BORDER_TOTAL
        c_uf.number_format = FMT_INT_M

        c_sb = ws_proj.cell(
            proj_rows["sbc"],
            col,
            f"={cl}{proj_rows['rev']}*'Assumptions & Scenarios'!{assump_cl}{scenario_row_map['active']['sbc_pct_rev']}",
        )
        c_sb.font = FONT_LINK
        c_sb.number_format = FMT_INT_M

        c_xs = ws_proj.cell(proj_rows["fcf_ex_sbc"], col, f"={cl}{proj_rows['ufcf']}-{cl}{proj_rows['sbc']}")
        c_xs.font = FONT_FORMULA_BOLD
        c_xs.number_format = FMT_INT_M

    # Dedicated Static Scenario Cash Flow Strips on Historical & Forecast (rows 21..38) so Base/Bull/Bear prices evaluate live simultaneously!
    last_hist_rev_cell = f"{get_column_letter(2 + n_hist)}{proj_rows['rev']}"
    sc_strip_rows: dict[str, dict[str, int]] = {}
    r_cursor = 21
    for sc_key in ("base", "bull", "bear"):
        _style_section_bar(ws_proj, r_cursor, f"Simultaneous Scenario Strip: {sc_key.upper()} Case ($M)", tot_cols_proj)
        r_rev_s = r_cursor + 1
        r_ebitda_s = r_cursor + 2
        r_cf_s = r_cursor + 3
        sc_strip_rows[sc_key] = {"rev": r_rev_s, "ebitda": r_ebitda_s, "cf": r_cf_s}
        ws_proj.cell(r_rev_s, 1, f"{sc_key.title()} Revenue").font = FONT_FORMULA
        ws_proj.cell(r_ebitda_s, 1, f"{sc_key.title()} EBITDA").font = FONT_FORMULA
        ws_proj.cell(r_cf_s, 1, f"{sc_key.title()} {cf_label}").font = FONT_FORMULA_BOLD

        for j in range(n_fc):
            col = 3 + n_hist + j
            cl = get_column_letter(col)
            prev_rev_ref = last_hist_rev_cell if j == 0 else f"{get_column_letter(col - 1)}{r_rev_s}"
            acl = get_column_letter(3 + j)
            rmap = scenario_row_map[sc_key]

            cr = ws_proj.cell(
                r_rev_s, col, f"={prev_rev_ref}*(1+'Assumptions & Scenarios'!{acl}{rmap['revenue_growth']})"
            )
            cr.font = FONT_LINK
            cr.number_format = FMT_INT_M

            ce = ws_proj.cell(
                r_ebitda_s,
                col,
                f"={cl}{r_rev_s}*('Assumptions & Scenarios'!{acl}{rmap['ebit_margin']}+'Assumptions & Scenarios'!{acl}{rmap['da_pct_rev']})",
            )
            ce.font = FONT_LINK
            ce.number_format = FMT_INT_M

            nopat_expr = f"({cl}{r_rev_s}*'Assumptions & Scenarios'!{acl}{rmap['ebit_margin']}*(1-'Assumptions & Scenarios'!{acl}{rmap['tax_rate']}))"
            da_expr = f"({cl}{r_rev_s}*'Assumptions & Scenarios'!{acl}{rmap['da_pct_rev']})"
            cx_expr = f"({cl}{r_rev_s}*'Assumptions & Scenarios'!{acl}{rmap['capex_pct_rev']})"
            nw_expr = f"(({cl}{r_rev_s}-{prev_rev_ref})*'Assumptions & Scenarios'!{acl}{rmap['nwc_pct_delta_rev']})"
            cf_expr = (
                f"={nopat_expr}-{cx_expr}-{nw_expr}"
                if model_type == "financials_ddm"
                else f"={nopat_expr}+{da_expr}-{cx_expr}-{nw_expr}"
            )
            ccf = ws_proj.cell(r_cf_s, col, cf_expr)
            ccf.font = FONT_FORMULA_BOLD
            ccf.number_format = FMT_INT_M

        r_cursor += 5

    # =========================================================================
    # TAB 4: WACC & INTRINSIC VALUE
    # =========================================================================
    max_c_dcf = max(8, 2 + n_fc)
    _style_banner(ws_dcf, f"{meta['ticker']} - Discount Rate (WACC / Ke), DCF & Sensitivity Matrix", subtitle, max_c_dcf)
    _style_section_bar(ws_dcf, 4, "1. Cost of Capital & Balance Sheet Bridge Inputs", max_c_dcf)

    # Left block (Cols A-B): WACC / Ke Build; Right block (Cols D-E): Capital Structure & Bridge
    wacc_left = [
        (5, "Risk-Free Rate (Rf)", float(wi["risk_free_rate"]), FMT_PCT2, True),
        (6, "Equity Risk Premium (ERP)", float(wi["equity_risk_premium"]), FMT_PCT2, True),
        (7, "Beta (Levered)", float(wi["beta"]), "0.00", True),
        (8, "Specific / Size Risk Premium", float(wi.get("specific_risk_premium", 0.0)), FMT_PCT2, True),
        (9, "Cost of Equity (Ke) - CAPM", "=B5+B7*B6+B8", FMT_PCT2, False),
        (10, "Pre-Tax Cost of Debt (Kd)", float(wi["pretax_cost_of_debt"]), FMT_PCT2, True),
        (11, "Marginal Tax Rate", float(wi["marginal_tax_rate"]), FMT_PCT2, True),
        (12, "After-Tax Cost of Debt", "=B10*(1-B11)", FMT_PCT2, False),
        (13, "Equity Weight (%)", "=E7/E9", FMT_PCT, False),
        (14, "Debt Weight (%)", "=E8/E9", FMT_PCT, False),
        (
            15,
            "Applied Discount Rate (WACC / Ke)",
            "=B9" if model_type == "financials_ddm" else "=B9*B13+B12*B14",
            FMT_PCT2,
            False,
        ),
        (16, "Terminal Perpetuity Growth Rate (g)", float(wi["terminal_growth_rate"]), FMT_PCT2, True),
        (17, "Terminal Exit Multiple (x)", float(wi["exit_multiple"]), FMT_MULT, True),
    ]
    for r, lbl, val, fmt, is_inp in wacc_left:
        ws_dcf.cell(r, 1, lbl).font = FONT_FORMULA_BOLD if r in (9, 15) else FONT_FORMULA
        c = ws_dcf.cell(r, 2, val)
        c.font = FONT_INPUT if is_inp else (FONT_FORMULA_BOLD if r in (9, 15) else FONT_FORMULA)
        if is_inp:
            c.fill = FILL_INPUT
        elif r == 15:
            c.fill = FILL_ACCENT
        c.number_format = fmt
        c.border = BORDER_DATA

    bridge_right = [
        (5, "Current Share Price ($)", float(meta["current_price"]), FMT_CURR, True),
        (6, "Diluted Shares Outstanding (M)", float(meta["diluted_shares_m"]), FMT_SHARES, True),
        (7, "Market Capitalization ($M)", "=E5*E6", FMT_INT_M, False),
        (8, "Total Debt ($M)", float(meta["total_debt_m"]), FMT_INT_M, True),
        (9, "Total Market Capitalization ($M)", "=E7+E8", FMT_INT_M, False),
        (10, "Cash & Marketable Securities ($M)", float(meta["cash_and_investments_m"]), FMT_INT_M, True),
        (11, "Preferred Stock ($M)", float(meta.get("preferred_stock_m", 0.0)), FMT_INT_M, True),
        (12, "Minority Interest ($M)", float(meta.get("minority_interest_m", 0.0)), FMT_INT_M, True),
        (13, "Net Debt ($M)", "=E8-E10", FMT_INT_M, False),
        (14, "Current Enterprise Value ($M)", "=E7+E8+E11+E12-E10", FMT_INT_M, False),
    ]
    for r, lbl, val, fmt, is_inp in bridge_right:
        ws_dcf.cell(r, 4, lbl).font = FONT_FORMULA_BOLD if r in (7, 14) else FONT_FORMULA
        c = ws_dcf.cell(r, 5, val)
        c.font = FONT_INPUT if is_inp else FONT_FORMULA_BOLD
        if is_inp:
            c.fill = FILL_INPUT
        c.number_format = fmt
        c.border = BORDER_DATA

    ws_dcf.cell(18, 1, "WACC / Discount Rationale:").font = FONT_TBL_HDR
    ws_dcf.cell(18, 2, wi.get("rationale", "")).font = FONT_NOTE

    # Section 2: Explicit Forecast Discounting (Active Scenario)
    _style_section_bar(ws_dcf, 20, "2. Explicit Forecast Present Value Schedule (Active Scenario)", max_c_dcf)
    ws_dcf.cell(21, 1, "Projection Year").font = FONT_TBL_HDR
    ws_dcf.cell(22, 1, "Discount Period (Years)").font = FONT_FORMULA
    ws_dcf.cell(23, 1, cf_label).font = FONT_FORMULA_BOLD
    ws_dcf.cell(24, 1, "Terminal Driver Metric (EBITDA or Cash Flow)").font = FONT_FORMULA
    ws_dcf.cell(25, 1, "Discount Factor").font = FONT_FORMULA
    ws_dcf.cell(26, 1, "Present Value of Cash Flow ($M)").font = FONT_FORMULA_BOLD

    for j, yr in enumerate(years_fc):
        col = 2 + j
        cl = get_column_letter(col)
        proj_cl = get_column_letter(3 + n_hist + j)

        hy = ws_dcf.cell(21, col, f"{yr}E")
        hy.font = FONT_TBL_HDR
        hy.fill = FILL_SUBHDR
        hy.alignment = Alignment(horizontal="right")

        cp = ws_dcf.cell(22, col, j + 1)
        cp.font = FONT_INPUT
        cp.number_format = "0"

        ccf = ws_dcf.cell(23, col, f"='Historical & Forecast'!{proj_cl}{proj_rows['ufcf']}")
        ccf.font = FONT_LINK_BOLD
        ccf.number_format = FMT_INT_M

        term_r = proj_rows["ufcf"] if model_type in ("financials_ddm", "reit_affo") else proj_rows["ebitda"]
        ctm = ws_dcf.cell(24, col, f"='Historical & Forecast'!{proj_cl}{term_r}")
        ctm.font = FONT_LINK
        ctm.number_format = FMT_INT_M

        cdf = ws_dcf.cell(25, col, f"=1/((1+$B$15)^{cl}22)")
        cdf.font = FONT_FORMULA
        cdf.number_format = "0.0000"

        cpv = ws_dcf.cell(26, col, f"={cl}23*{cl}25")
        cpv.font = FONT_FORMULA_BOLD
        cpv.fill = FILL_TOTAL
        cpv.number_format = FMT_INT_M

    first_fc_cl = get_column_letter(2)
    last_fc_cl = get_column_letter(1 + n_fc)

    # Section 3: Dual Terminal Value & EV-to-Equity Bridge (Cols A-C: Perpetuity, Cols D-E: Exit Multiple)
    _style_section_bar(ws_dcf, 28, "3. Dual Terminal Value Cross-Check & Implied Share Price", max_c_dcf)
    ws_dcf.cell(29, 1, "Valuation Component").font = FONT_TBL_HDR
    ws_dcf.cell(29, 2, "Perpetuity Growth Method").font = FONT_TBL_HDR
    ws_dcf.cell(29, 3, "Exit Multiple Method").font = FONT_TBL_HDR
    ws_dcf.cell(29, 2).fill = FILL_SUBHDR
    ws_dcf.cell(29, 3).fill = FILL_SUBHDR

    bridge_calc_rows = [
        (30, "PV of Explicit Forecast Cash Flows ($M)", f"=SUM({first_fc_cl}26:{last_fc_cl}26)", f"=SUM({first_fc_cl}26:{last_fc_cl}26)", FMT_INT_M, False),
        (31, "Undiscounted Terminal Value ($M)", f"=({last_fc_cl}23*(1+$B$16))/($B$15-$B$16)", f"={last_fc_cl}24*$B$17", FMT_INT_M, False),
        (32, "PV of Terminal Value ($M)", f"=B31*{last_fc_cl}25", f"=C31*{last_fc_cl}25", FMT_INT_M, False),
        (33, "Implied Enterprise Value ($M)", "=B30+B32", "=C30+C32", FMT_INT_M, True),
        (
            34,
            "Implied Equity Value ($M)",
            "=B33" if model_type == "financials_ddm" else "=B33+$E$10-$E$8-$E$11-$E$12",
            "=C33" if model_type == "financials_ddm" else "=C33+$E$10-$E$8-$E$11-$E$12",
            FMT_INT_M,
            True,
        ),
        (35, "Implied Intrinsic Value per Share ($)", "=B34/$E$6", "=C34/$E$6", FMT_CURR, True),
        (36, "Implied Upside / (Downside) vs Current (%)", "=(B35/$E$5)-1", "=(C35/$E$5)-1", FMT_PCT, False),
        (
            37,
            "Cross-Check: Implied Exit Multiple / Implied g",
            f"=B31/{last_fc_cl}24",
            f"=($B$15*C31-{last_fc_cl}23)/(C31+{last_fc_cl}23)",
            None,
            False,
        ),
    ]
    for r, lbl, f_perp, f_mult, fmt, is_b in bridge_calc_rows:
        ws_dcf.cell(r, 1, lbl).font = FONT_FORMULA_BOLD if is_b else FONT_FORMULA
        cp = ws_dcf.cell(r, 2, f_perp)
        cm = ws_dcf.cell(r, 3, f_mult)
        cp.font = FONT_FORMULA_BOLD if is_b else FONT_FORMULA
        cm.font = FONT_FORMULA_BOLD if is_b else FONT_FORMULA
        if r == 35:
            cp.fill = FILL_ACCENT
            cm.fill = FILL_ACCENT
            cp.border = BORDER_TOTAL
            cm.border = BORDER_TOTAL
        if fmt:
            cp.number_format = fmt
            cm.number_format = fmt
        else:
            cp.number_format = FMT_MULT
            cm.number_format = FMT_PCT2

    # Section 4: Simultaneous Scenario Valuation Summary (Base / Bull / Bear Perpetuity & Exit Multiple)
    _style_section_bar(ws_dcf, 39, "4. Simultaneous Bull / Base / Bear Scenario Matrix (Live Formulas)", max_c_dcf)
    ws_dcf.cell(40, 1, "Scenario").font = FONT_TBL_HDR
    ws_dcf.cell(40, 2, "PV Explicit CFs ($M)").font = FONT_TBL_HDR
    ws_dcf.cell(40, 3, "PV Terminal (Perp) ($M)").font = FONT_TBL_HDR
    ws_dcf.cell(40, 4, "Intrinsic Price - Perp ($)").font = FONT_TBL_HDR
    ws_dcf.cell(40, 5, "Intrinsic Price - Exit Mult ($)").font = FONT_TBL_HDR
    for col_i in range(1, 6):
        ws_dcf.cell(40, col_i).fill = FILL_SUBHDR

    sc_summary_rows: dict[str, int] = {}
    first_proj_fc_cl = get_column_letter(3 + n_hist)
    last_proj_fc_cl = get_column_letter(2 + n_hist + n_fc)
    for idx_s, sc_key in enumerate(("base", "bull", "bear")):
        r_s = 41 + idx_s
        sc_summary_rows[sc_key] = r_s
        r_cf_strip = sc_strip_rows[sc_key]["cf"]
        r_eb_strip = sc_strip_rows[sc_key]["cf"] if model_type in ("financials_ddm", "reit_affo") else sc_strip_rows[sc_key]["ebitda"]

        ws_dcf.cell(r_s, 1, f"{sc_key.title()} Case").font = FONT_FORMULA_BOLD
        # NPV($B$15, range) computes exact PV of Year 1..N cash flows!
        c_pv = ws_dcf.cell(
            r_s, 2, f"=NPV($B$15,'Historical & Forecast'!{first_proj_fc_cl}{r_cf_strip}:{last_proj_fc_cl}{r_cf_strip})"
        )
        c_pv.font = FONT_LINK
        c_pv.number_format = FMT_INT_M

        c_tvp = ws_dcf.cell(
            r_s,
            3,
            f"=(('Historical & Forecast'!{last_proj_fc_cl}{r_cf_strip}*(1+$B$16))/($B$15-$B$16))*{last_fc_cl}25",
        )
        c_tvp.font = FONT_LINK
        c_tvp.number_format = FMT_INT_M

        bridge_adj = "" if model_type == "financials_ddm" else "+$E$10-$E$8-$E$11-$E$12"
        c_pp = ws_dcf.cell(r_s, 4, f"=(B{r_s}+C{r_s}{bridge_adj})/$E$6")
        c_pp.font = FONT_FORMULA_BOLD
        c_pp.number_format = FMT_CURR

        tv_m_pv = f"(('Historical & Forecast'!{last_proj_fc_cl}{r_eb_strip}*$B$17)*{last_fc_cl}25)"
        c_pm = ws_dcf.cell(r_s, 5, f"=(B{r_s}+{tv_m_pv}{bridge_adj})/$E$6")
        c_pm.font = FONT_FORMULA_BOLD
        c_pm.number_format = FMT_CURR

    # Section 5: 5x5 2D Sensitivity Matrix (WACC vs Terminal Growth Rate)
    _style_section_bar(ws_dcf, 46, "5. Sensitivity Table: Intrinsic Share Price ($) - Discount Rate vs. Terminal Growth", max_c_dcf)
    ws_dcf.cell(47, 1, "WACC \\ Term. Growth").font = FONT_TBL_HDR
    g_deltas = [-0.010, -0.005, 0.0, 0.005, 0.010]
    w_deltas = [-0.010, -0.005, 0.0, 0.005, 0.010]

    for j_g, dg in enumerate(g_deltas):
        col = 2 + j_g
        c_gh = ws_dcf.cell(47, col, f"=$B$16+({dg})")
        c_gh.font = FONT_TBL_HDR
        c_gh.fill = FILL_SUBHDR
        c_gh.number_format = FMT_PCT2

    for i_w, dw in enumerate(w_deltas):
        r_w = 48 + i_w
        c_wh = ws_dcf.cell(r_w, 1, f"=$B$15+({dw})")
        c_wh.font = FONT_TBL_HDR
        c_wh.fill = FILL_SUBHDR
        c_wh.number_format = FMT_PCT2

        for j_g in range(len(g_deltas)):
            col = 2 + j_g
            g_ref = f"{get_column_letter(col)}$47"
            w_ref = f"$A{r_w}"
            pv_cf_expr = f"NPV({w_ref},{first_fc_cl}$23:{last_fc_cl}$23)"
            pv_tv_expr = f"(({last_fc_cl}$23*(1+{g_ref}))/({w_ref}-{g_ref}))/((1+{w_ref})^{n_fc})"
            bridge_adj = "" if model_type == "financials_ddm" else "+$E$10-$E$8-$E$11-$E$12"
            scell = ws_dcf.cell(r_w, col, f"=({pv_cf_expr}+{pv_tv_expr}{bridge_adj})/$E$6")
            scell.font = FONT_FORMULA_BOLD if (i_w == 2 and j_g == 2) else FONT_FORMULA
            if i_w == 2 and j_g == 2:
                scell.fill = FILL_ACCENT
            scell.number_format = FMT_CURR
            scell.border = BORDER_DATA

    # =========================================================================
    # TAB 5: RELATIVE VALUATION
    # =========================================================================
    _style_banner(ws_comps, f"{meta['ticker']} - Peer Comparable Valuation Matrix", subtitle, 11)
    _style_section_bar(ws_comps, 4, "1. Comparable Companies Trading & Fundamental Matrix", 11)

    comp_headers = [
        ("Ticker", None),
        ("Company Name", None),
        ("Market Cap ($M)", FMT_INT_M),
        ("Enterprise Value ($M)", FMT_INT_M),
        ("Rev Growth (%)", FMT_PCT),
        ("EBITDA Margin (%)", FMT_PCT),
        ("ROE (%)", FMT_PCT),
        ("Forward P/E", FMT_MULT),
        ("EV / EBITDA", FMT_MULT),
        ("EV / Revenue", FMT_MULT),
        ("FCF Yield (%)", FMT_PCT),
    ]
    metric_col_idx = {
        "forward_pe": 8,
        "ev_to_ebitda": 9,
        "ev_to_revenue": 10,
        "fcf_yield": 11,
    }
    for c_i, (h_txt, _) in enumerate(comp_headers, start=1):
        hc = ws_comps.cell(5, c_i, h_txt)
        hc.font = FONT_TBL_HDR
        hc.fill = FILL_SUBHDR
        hc.border = BORDER_HDR

    peers = rv["peers"]
    p_start = 6
    for idx_p, p in enumerate(peers):
        r_p = p_start + idx_p
        vals_p = [
            p["ticker"],
            p["name"],
            p.get("market_cap_m"),
            p.get("ev_m"),
            p.get("rev_growth"),
            p.get("ebitda_margin"),
            p.get("roe"),
            p.get("forward_pe"),
            p.get("ev_to_ebitda"),
            p.get("ev_to_revenue"),
            p.get("fcf_yield"),
        ]
        for c_i, v in enumerate(vals_p, start=1):
            cell = ws_comps.cell(r_p, c_i, v)
            cell.font = FONT_INPUT if c_i >= 3 else FONT_FORMULA
            if c_i >= 3:
                cell.fill = FILL_INPUT
                cell.number_format = comp_headers[c_i - 1][1]
            cell.border = BORDER_DATA

    p_end = p_start + len(peers) - 1
    stat_rows = [
        (p_end + 2, "Peer Mean", "AVERAGE"),
        (p_end + 3, "Peer Median", "MEDIAN"),
        (p_end + 4, "25th Percentile", "P25"),
        (p_end + 5, "75th Percentile", "P75"),
    ]
    r_median = p_end + 3
    for r_st, st_lbl, fn_kind in stat_rows:
        ws_comps.cell(r_st, 1, st_lbl).font = FONT_FORMULA_BOLD
        ws_comps.cell(r_st, 1).fill = FILL_TOTAL
        for c_i in range(3, 12):
            cl = get_column_letter(c_i)
            rng = f"{cl}{p_start}:{cl}{p_end}"
            if fn_kind in ("AVERAGE", "MEDIAN"):
                f_str = f"={fn_kind}({rng})"
            elif fn_kind == "P25":
                f_str = f"=PERCENTILE.INC({rng},0.25)"
            else:
                f_str = f"=PERCENTILE.INC({rng},0.75)"
            sc = ws_comps.cell(r_st, c_i, f_str)
            sc.font = FONT_FORMULA_BOLD if r_st == r_median else FONT_FORMULA
            sc.fill = FILL_TOTAL
            sc.number_format = comp_headers[c_i - 1][1]
            sc.border = BORDER_DATA

    # Implied Relative Valuation Calibration Block
    r_cal = p_end + 7
    _style_section_bar(ws_comps, r_cal, "2. Selected Multiple Calibration & Implied Comps Share Price", 11)
    primary_m = rv["primary_metric"]
    sel_col_letter = get_column_letter(metric_col_idx.get(primary_m, 9))
    is_ev_mult = primary_m.startswith("ev_")

    cal_rows = [
        (r_cal + 1, "Selected Primary Multiple", primary_m, None, True),
        (r_cal + 2, "Peer Median Benchmark Multiple (x)", f"={sel_col_letter}{r_median}", FMT_MULT, False),
        (r_cal + 3, "Target Quality / Growth Premium (Discount) %", float(rv.get("premium_discount_pct", 0.0)), FMT_PCT, True),
        (r_cal + 4, "Applied Target Multiple (x)", f"=B{r_cal + 2}*(1+B{r_cal + 3})", FMT_MULT, False),
        (r_cal + 5, f"{meta['ticker']} Forward Metric ($M)", float(rv["company_forward_metric_m"]), FMT_INT_M, True),
        (
            r_cal + 6,
            "Implied Enterprise Value from Comps ($M)",
            f"=B{r_cal + 4}*B{r_cal + 5}" if is_ev_mult else f"=B{r_cal + 7}-'WACC & Intrinsic Value'!E10+'WACC & Intrinsic Value'!E8",
            FMT_INT_M,
            False,
        ),
        (
            r_cal + 7,
            "Implied Equity Value from Comps ($M)",
            f"=B{r_cal + 6}+'WACC & Intrinsic Value'!E10-'WACC & Intrinsic Value'!E8-'WACC & Intrinsic Value'!E11-'WACC & Intrinsic Value'!E12"
            if is_ev_mult
            else f"=B{r_cal + 4}*B{r_cal + 5}",
            FMT_INT_M,
            False,
        ),
        (r_cal + 8, "Implied Share Price - Relative Valuation ($)", f"=B{r_cal + 7}/'WACC & Intrinsic Value'!E6", FMT_CURR, False),
    ]
    r_comps_price = r_cal + 8
    for r_c, lbl, val, fmt, is_inp in cal_rows:
        ws_comps.cell(r_c, 1, lbl).font = FONT_FORMULA_BOLD if r_c == r_comps_price else FONT_FORMULA
        cc = ws_comps.cell(r_c, 2, val)
        cc.font = FONT_INPUT if is_inp else (FONT_FORMULA_BOLD if r_c == r_comps_price else FONT_FORMULA)
        if is_inp:
            cc.fill = FILL_INPUT
        elif r_c == r_comps_price:
            cc.fill = FILL_ACCENT
            cc.border = BORDER_TOTAL
        if fmt:
            cc.number_format = fmt

    pd_basis = ab["premium_discount_pct"]
    ws_comps.cell(r_cal + 9, 1, "Premium / Discount Basis:").font = FONT_TBL_HDR
    c_pdb = ws_comps.cell(r_cal + 9, 2, _format_basis_tag(pd_basis))
    c_pdb.font = FONT_FORMULA_BOLD if pd_basis.get("basis_type") == "thesis" else FONT_NOTE
    if pd_basis.get("basis_type") == "thesis":
        c_pdb.fill = FILL_ACCENT
    ws_comps.cell(r_cal + 10, 1, "Historical / Peer Anchor:").font = FONT_TBL_HDR
    ws_comps.cell(r_cal + 10, 2, pd_basis.get("historical_anchor", "")).font = FONT_NOTE
    ws_comps.cell(r_cal + 11, 1, "Premium / Discount Rationale:").font = FONT_TBL_HDR
    ws_comps.cell(r_cal + 11, 2, pd_basis.get("rationale", rv.get("premium_discount_rationale", ""))).font = FONT_NOTE

    # =========================================================================
    # TAB 1: EXECUTIVE SUMMARY
    # =========================================================================
    _style_banner(ws_exec, f"{meta['company_name']} ({meta['ticker']}) - Valuation Executive Summary", subtitle, 7)
    _style_section_bar(ws_exec, 4, "1. Investment Rating, Target Price & IPS Hurdle Scorecard", 7)

    bw = meta["blend_weights"]
    exec_top = [
        (5, "Current Share Price ($)", "='WACC & Intrinsic Value'!E5", FMT_CURR, FONT_LINK),
        (6, "Blended 12M Target Price ($)", "=SUMPRODUCT(C14:C16,D14:D16)", FMT_CURR, FONT_FORMULA_BOLD),
        (7, "Implied Upside / (Downside) (%)", "=(B6/B5)-1", FMT_PCT, FONT_FORMULA_BOLD),
        (8, "IPS Minimum Buy Upside Hurdle (%)", float(meta["ips_buy_upside_hurdle"]), FMT_PCT, FONT_INPUT),
        (9, "IPS Sell Downside Trigger (%)", float(meta["ips_sell_upside_hurdle"]), FMT_PCT, FONT_INPUT),
        (10, "IPS-Aligned Coverage Rating", '=IF(B7>=B8,"BUY",IF(B7<=B9,"SELL","HOLD"))', None, FONT_FORMULA_BOLD),
    ]
    for r, lbl, val, fmt, fnt in exec_top:
        ws_exec.cell(r, 1, lbl).font = FONT_FORMULA_BOLD if r in (6, 7, 10) else FONT_FORMULA
        c = ws_exec.cell(r, 2, val)
        c.font = fnt
        if r in (6, 10):
            c.fill = FILL_ACCENT
            c.border = BORDER_TOTAL
        elif fnt == FONT_INPUT:
            c.fill = FILL_INPUT
            c.border = BORDER_DATA
        if fmt:
            c.number_format = fmt

    _style_section_bar(ws_exec, 12, "2. Blended Target Price Weights & Valuation Football Field", 7)
    for idx_h, h_txt in enumerate(("Valuation Methodology", "Notes / Basis", "Implied Price ($)", "Target Weight (%)", "Weighted Contribution ($)", "vs. Current (%)"), start=1):
        hc = ws_exec.cell(13, idx_h, h_txt)
        hc.font = FONT_TBL_HDR
        hc.fill = FILL_SUBHDR
        hc.border = BORDER_HDR

    blend_methods = [
        (14, "Intrinsic Value - Perpetuity Growth", "Base Case DCF / DDM", "='WACC & Intrinsic Value'!D41", float(bw["dcf_perpetuity"])),
        (15, "Intrinsic Value - Exit Multiple", "Base Case Exit Multiple Cross-Check", "='WACC & Intrinsic Value'!E41", float(bw["dcf_exit_multiple"])),
        (16, "Relative Valuation - Peer Comps", f"Peer Median {primary_m} w/ Calibrated Adj.", f"='Relative Valuation'!B{r_comps_price}", float(bw["relative_comps"])),
    ]
    for r, m_lbl, m_note, p_link, w_val in blend_methods:
        ws_exec.cell(r, 1, m_lbl).font = FONT_FORMULA_BOLD
        ws_exec.cell(r, 2, m_note).font = FONT_NOTE
        cp = ws_exec.cell(r, 3, p_link)
        cp.font = FONT_LINK_BOLD
        cp.number_format = FMT_CURR
        cw = ws_exec.cell(r, 4, w_val)
        cw.font = FONT_INPUT
        cw.fill = FILL_INPUT
        cw.number_format = FMT_PCT
        ccont = ws_exec.cell(r, 5, f"=C{r}*D{r}")
        ccont.font = FONT_FORMULA
        ccont.number_format = FMT_CURR
        cup = ws_exec.cell(r, 6, f"=(C{r}/$B$5)-1")
        cup.font = FONT_FORMULA
        cup.number_format = FMT_PCT

    ws_exec.cell(17, 1, "Total Blended Target Price").font = FONT_FORMULA_BOLD
    ws_exec.cell(17, 4, "=SUM(D14:D16)").font = FONT_FORMULA_BOLD
    ws_exec.cell(17, 4).number_format = FMT_PCT
    ws_exec.cell(17, 5, "=SUM(E14:E16)").font = FONT_FORMULA_BOLD
    ws_exec.cell(17, 5).fill = FILL_ACCENT
    ws_exec.cell(17, 5).border = BORDER_TOTAL
    ws_exec.cell(17, 5).number_format = FMT_CURR
    ws_exec.cell(17, 6, "=(E17/$B$5)-1").font = FONT_FORMULA_BOLD
    ws_exec.cell(17, 6).number_format = FMT_PCT

    _style_section_bar(ws_exec, 19, "3. Scenario Range (Bull / Base / Bear Intrinsic Value)", 7)
    for idx_h, h_txt in enumerate(("Scenario", "Perpetuity Price ($)", "Upside (%)", "Exit Multiple Price ($)", "Upside (%)"), start=1):
        hc = ws_exec.cell(20, idx_h, h_txt)
        hc.font = FONT_TBL_HDR
        hc.fill = FILL_SUBHDR

    for idx_s, sc_key in enumerate(("bull", "base", "bear")):
        r_e = 21 + idx_s
        r_dcf_s = sc_summary_rows[sc_key]
        ws_exec.cell(r_e, 1, f"{sc_key.title()} Case").font = FONT_FORMULA_BOLD
        c1 = ws_exec.cell(r_e, 2, f"='WACC & Intrinsic Value'!D{r_dcf_s}")
        c1.font = FONT_LINK_BOLD
        c1.number_format = FMT_CURR
        c2 = ws_exec.cell(r_e, 3, f"=(B{r_e}/$B$5)-1")
        c2.font = FONT_FORMULA
        c2.number_format = FMT_PCT
        c3 = ws_exec.cell(r_e, 4, f"='WACC & Intrinsic Value'!E{r_dcf_s}")
        c3.font = FONT_LINK
        c3.number_format = FMT_CURR
        c4 = ws_exec.cell(r_e, 5, f"=(D{r_e}/$B$5)-1")
        c4.font = FONT_FORMULA
        c4.number_format = FMT_PCT

    # Auto-fit column widths comfortably across all sheets + freeze panes
    for ws in wb.worksheets:
        ws.freeze_panes = "C6" if ws.title in ("Historical & Forecast", "Assumptions & Scenarios") else "A5"
        for col_cells in ws.columns:
            col_idx = col_cells[0].column
            col_ltr = get_column_letter(col_idx)
            max_len = 12
            for cell in col_cells:
                if cell.row in (1, 2):
                    continue
                val_str = str(cell.value or "")
                if val_str.startswith("="):
                    max_len = max(max_len, 14)
                else:
                    max_len = max(max_len, min(len(val_str) + 4, 48))
            ws.column_dimensions[col_ltr].width = max_len

    out_xlsx.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_xlsx)

    # Audit workbook formula integrity
    audit = verify_workbook_formulas(out_xlsx)
    shadow = _compute_python_shadow(spec)
    shadow["workbook_path"] = str(out_xlsx)
    shadow["formula_audit"] = audit
    return shadow


def verify_workbook_formulas(xlsx_path: Path) -> dict[str, Any]:
    wb = openpyxl.load_workbook(xlsx_path, data_only=False)
    formula_count = 0
    error_cells: list[str] = []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                v = cell.value
                if isinstance(v, str):
                    if v.startswith("="):
                        formula_count += 1
                    for tok in EXCEL_ERROR_TOKENS:
                        if tok in v:
                            error_cells.append(f"{ws.title}!{cell.coordinate}: {v}")
    if error_cells:
        raise ValueError(f"Workbook contains Excel error literals: {error_cells}")
    if formula_count < 80:
        raise ValueError(f"Expected >=80 live Excel formulas, found only {formula_count}.")
    return {
        "status": "PASS",
        "sheets": wb.sheetnames,
        "live_formula_cells": formula_count,
        "error_cells": error_cells,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate live-formula Excel valuation workbook (.xlsx)")
    parser.add_argument("--spec", help="Path to valuation_spec.json")
    parser.add_argument("--out-xlsx", help="Output .xlsx path (default Output/models/<TICKER>_valuation.xlsx)")
    parser.add_argument("--out-summary", help="Output summary JSON path (default memory/<TICKER>/valuation_summary.json)")
    parser.add_argument("--write-sample-spec", help="Write a complete starter valuation_spec.json to this path and exit")
    args = parser.parse_args()

    if args.write_sample_spec:
        sp = Path(args.write_sample_spec)
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text(json.dumps(SAMPLE_SPEC, indent=2), encoding="utf-8")
        print(f"Wrote sample valuation spec to {sp}")
        return 0

    if not args.spec:
        print("Error: --spec is required unless --write-sample-spec is used.", file=sys.stderr)
        return 1

    try:
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        tk = spec["meta"]["ticker"].upper()
        out_xlsx = Path(args.out_xlsx or f"Output/models/{tk}_valuation.xlsx")
        out_sum = Path(args.out_summary or f"memory/{tk}/valuation_summary.json")

        summary = build_valuation_workbook(spec, out_xlsx)
        out_sum.parent.mkdir(parents=True, exist_ok=True)
        out_sum.write_text(json.dumps(summary, indent=2), encoding="utf-8")

        print(
            f"Built {out_xlsx} ({summary['formula_audit']['live_formula_cells']} live formulas, 0 errors) | "
            f"Target: ${summary['blended_target_price']:.2f} ({summary['implied_upside_pct']:+.1f}%) -> {summary['rating']}"
        )
        print(f"Saved valuation summary JSON to {out_sum}")
    except PermissionError as exc:
        print(
            f"Valuation build error: {exc} (file may be open in Excel; close it in Excel or pass an alternate --out-xlsx path).",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(f"Valuation build error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

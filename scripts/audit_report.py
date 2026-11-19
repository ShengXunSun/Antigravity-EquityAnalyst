#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "markdown>=3.6",
#     "beautifulsoup4>=4.12.0",
#     "reportlab>=4.2.0",
# ]
# ///
"""Audit initiation report against valuation_summary.json, enforce plain prose, and export institutional PDF."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any

import markdown
from bs4 import BeautifulSoup, NavigableString, Tag
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

REQUIRED_SECTION_PATTERNS: list[tuple[str, str]] = [
    ("Quick Conclusion", r"(?i)^#{1,3}\s+.*(quick conclusion|executive summary|initiation summary)"),
    ("Investment Thesis Summary", r"(?i)^#{1,3}\s+.*(thesis summary|investment summary)"),
    ("Stock Selection & IPS Fit", r"(?i)^#{1,3}\s+.*(selection rationale|ips fit|screening rationale)"),
    ("Company Summary", r"(?i)^#{1,3}\s+.*(company summary|business overview|company overview)"),
    ("Industry Summary", r"(?i)^#{1,3}\s+.*(industry|competitive landscape)"),
    ("Financial Summary & Consensus Table", r"(?i)^#{1,3}\s+.*(financial summary|consensus|historical.*projected)"),
    ("Detailed Variant Thesis", r"(?i)^#{1,3}\s+.*(detailed.*thesis|variant.*thesis|investment thesis)"),
    ("Valuation", r"(?i)^#{1,3}\s+.*valuation"),
    ("Risks, Catalysts & Exit Triggers", r"(?i)^#{1,3}\s+.*(risk|catalyst|thesis-break|exit trigger)"),
]

BANNED_SLOP_PATTERNS: list[tuple[str, str]] = [
    ("AI vocabulary", r"\b(delve|delving|tapestry|pivotal|testament|underscores|interplay|intricate|vibrant|fostering|garner)\b"),
    ("Fancy 'is' verb", r"\b(serves as|stands as|boasts)\b"),
    ("Vague attribution", r"\b(experts believe|industry reports suggest|some critics argue|observers note)\b"),
    ("Chatbot artifact", r"\b(i hope this helps|let me know if you|the future looks bright)\b"),
    ("Em-dash overuse", r"—"),
]

PRINT_CSS = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  body {{ font-family: Georgia, 'Times New Roman', serif; max-width: 880px; margin: 36px auto; padding: 0 24px; color: #1a202c; line-height: 1.58; font-size: 15px; }}
  h1, h2, h3 {{ font-family: 'Segoe UI', Calibri, Arial, sans-serif; color: #1B365D; margin-top: 1.4em; }}
  h1 {{ border-bottom: 3px solid #1B365D; padding-bottom: 8px; font-size: 26px; }}
  h2 {{ border-bottom: 1px solid #CBD5E0; padding-bottom: 4px; font-size: 19px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 16px 0; font-family: 'Segoe UI', Calibri, sans-serif; font-size: 13px; }}
  th {{ background: #1B365D; color: #ffffff; text-align: left; padding: 7px 10px; }}
  td {{ border-bottom: 1px solid #E2E8F0; padding: 6px 10px; }}
  tr:nth-child(even) td {{ background: #F8FAFC; }}
  blockquote {{ border-left: 4px solid #2C5282; margin: 14px 0; padding: 6px 14px; background: #F0F4F8; }}
  code {{ background: #EDF2F7; padding: 1px 4px; border-radius: 3px; font-size: 13px; }}
  @media print {{ body {{ margin: 12mm; font-size: 11pt; }} table {{ page-break-inside: avoid; }} }}
</style>
</head>
<body>
{body}
</body>
</html>
"""

UNICODE_FALLBACK_MAP = {
    "\u2192": "->",
    "\u2190": "<-",
    "\u21d2": "=>",
    "\u2265": ">=",
    "\u2264": "<=",
    "\u2248": "~",
    "\u2260": "!=",
    "\u2212": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u00a0": " ",
}

DRIVER_HUMAN_ALIASES: dict[str, str] = {
    "revenue_growth": r"(revenue_growth|revenue growth|top-line growth|revenue cagr)",
    "ebit_margin": r"(ebit_margin|ebit margin|operating margin)",
    "capex_pct_rev": r"(capex_pct_rev|capex|capital expenditure)",
    "premium_discount_pct": r"(premium_discount_pct|premium|discount|applied multiple|peer median)",
    "tax_rate": r"(tax_rate|tax rate|effective tax)",
    "da_pct_rev": r"(da_pct_rev|d&a|depreciation)",
    "nwc_pct_delta_rev": r"(nwc_pct_delta_rev|working capital|\bnwc\b)",
    "sbc_pct_rev": r"(sbc_pct_rev|stock-based comp|\bsbc\b)",
}


def _extract_h2_section(md_text: str, heading_pat: str) -> str:
    lines = md_text.splitlines()
    start_idx: int | None = None
    for idx, line in enumerate(lines):
        if re.search(heading_pat, line):
            start_idx = idx
            break
    if start_idx is None:
        return ""
    end_idx = len(lines)
    for idx in range(start_idx + 1, len(lines)):
        if re.match(r"^##\s+\S", lines[idx]):
            end_idx = idx
            break
    return "\n".join(lines[start_idx:end_idx])


def _extract_pillar_block(sec7_text: str, pillar_id: str) -> str:
    lines = sec7_text.splitlines()
    start_idx: int | None = None
    for idx, line in enumerate(lines):
        if re.match(r"^#{3,4}\s+", line) and re.search(rf"\b{re.escape(pillar_id)}\b", line):
            start_idx = idx
            break
    if start_idx is None:
        return ""
    end_idx = len(lines)
    for idx in range(start_idx + 1, len(lines)):
        if re.match(r"^#{2,4}\s+", lines[idx]):
            end_idx = idx
            break
    return "\n".join(lines[start_idx:end_idx])


def _currency_symbol(currency: str) -> str:
    code = (currency or "USD").strip().upper()
    return {
        "USD": "$",
        "HKD": "HK$",
        "CNY": "RMB ",
        "RMB": "RMB ",
        "EUR": "€",
        "GBP": "£",
        "JPY": "¥",
    }.get(code, f"{code} ")


def _number_appears(text: str, target: float, pct: bool = False) -> bool:
    """Check if target (or standard 1- or 2-decimal rounded string) appears in report text."""
    candidates = {
        f"{target:.2f}",
        f"{target:.1f}",
        f"{target:,.2f}",
        f"{target:,.1f}",
        f"{round(target):,}",
    }
    if pct:
        candidates |= {f"{target:+.2f}", f"{target:+.1f}"}
    return any(c in text for c in candidates)


def audit_report(report_md_path: Path, valuation_summary_path: Path) -> dict[str, Any]:
    md_text = report_md_path.read_text(encoding="utf-8")
    val = json.loads(valuation_summary_path.read_text(encoding="utf-8"))

    errors: list[str] = []
    warnings: list[str] = []

    # 1. Section completeness check
    for sec_name, pat in REQUIRED_SECTION_PATTERNS:
        if not re.search(pat, md_text, flags=re.MULTILINE):
            errors.append(f"Missing required report section heading matching: {sec_name}")

    # 2. Model-to-Report numerical & rating consistency
    csym = _currency_symbol(str(val.get("currency", "USD")))
    ticker = str(val["ticker"]).upper()
    if ticker not in md_text:
        errors.append(f"Ticker '{ticker}' does not appear in report.")

    rating = str(val["rating"]).upper()
    if not re.search(rf"\b{re.escape(rating)}\b", md_text, flags=re.IGNORECASE):
        errors.append(f"Model rating '{rating}' not found in report text.")

    tp = float(val["blended_target_price"])
    if not _number_appears(md_text, tp):
        errors.append(
            f"Blended Target Price ({csym}{tp:.2f}) from valuation_summary.json does not appear in report."
        )

    cp = float(val["current_price"])
    if not _number_appears(md_text, cp):
        errors.append(f"Current Share Price ({csym}{cp:.2f}) does not appear in report.")

    upside = float(val["implied_upside_pct"])
    if not _number_appears(md_text, upside, pct=True) and not _number_appears(md_text, abs(upside)):
        errors.append(f"Implied upside ({upside:+.1f}%) from model does not appear in report.")

    wacc_pct = float(val["discount_rate_wacc_or_ke"]) * 100.0
    if not _number_appears(md_text, wacc_pct):
        warnings.append(
            f"Discount rate ({wacc_pct:.2f}% / {wacc_pct:.1f}%) not explicitly cited in report."
        )

    bull_p = float(val["scenarios"]["bull"]["share_price_perpetuity"])
    bear_p = float(val["scenarios"]["bear"]["share_price_perpetuity"])
    if not _number_appears(md_text, bull_p):
        warnings.append(f"Bull case intrinsic price ({csym}{bull_p:.2f}) not explicitly cited in report.")
    if not _number_appears(md_text, bear_p):
        warnings.append(f"Bear case intrinsic price ({csym}{bear_p:.2f}) not explicitly cited in report.")

    # 2B. Bidirectional Thesis-to-Model check in Section 7 (Detailed Variant Thesis)
    pillars = val.get("thesis_pillars", [])
    ab = val.get("assumption_basis", {})
    if not pillars:
        errors.append(
            "valuation_summary.json is missing 'thesis_pillars'; rebuild the Excel model with updated valuation_excel.py."
        )
    else:
        sec7 = _extract_h2_section(md_text, r"(?i)^##\s+.*(detailed.*thesis|variant.*thesis)")
        if not sec7:
            errors.append("Could not locate H2 Section 7 (Detailed Variant Thesis) for per-pillar Model Impact audit.")
        else:
            for p in pillars:
                pid = str(p.get("id", "")).strip()
                ptitle = str(p.get("title", "")).strip()
                pblock = _extract_pillar_block(sec7, pid)
                if not pblock:
                    errors.append(
                        f"Section 7 must contain a dedicated H3/H4 subsection heading citing Thesis Pillar '{pid}' ('{ptitle}')."
                    )
                    continue
                if not re.search(r"(?i)model\s+(impact|translation)", pblock):
                    errors.append(
                        f"Thesis Pillar '{pid}' in Section 7 is missing a mandatory 'Model Impact' block explaining how {pid} drives 5-year model numbers and Bull/Bear flex."
                    )
                for drv in p.get("impacted_drivers", []):
                    alias_pat = DRIVER_HUMAN_ALIASES.get(drv, re.escape(drv))
                    if not re.search(alias_pat, pblock, flags=re.IGNORECASE):
                        errors.append(
                            f"Thesis Pillar '{pid}' in Section 7 must explicitly explain its impact on linked model driver '{drv}'."
                        )

    # 2C. Section 8 (Valuation) Model Assumptions & Basis Table check
    sec8 = _extract_h2_section(md_text, r"(?i)^##\s+.*valuation")
    if sec8 and ab:
        sec8_table_lines = [ln for ln in sec8.splitlines() if ln.strip().startswith("|")]
        sec8_tables_text = "\n".join(sec8_table_lines)
        if not re.search(r"(?i)\|\s*[^|]*basis[^|]*\|", sec8_tables_text):
            errors.append(
                "Section 8 (Valuation) must include a 'Model Assumptions & Basis Table' with a 'Basis' column distinguishing 'Thesis: T1..Tn' vs. 'Historical / Market Anchor'."
            )
        else:
            for key_drv in ("revenue_growth", "ebit_margin", "capex_pct_rev", "premium_discount_pct"):
                alias_pat = DRIVER_HUMAN_ALIASES[key_drv]
                if not re.search(alias_pat, sec8_tables_text, flags=re.IGNORECASE):
                    errors.append(
                        f"Section 8 Model Assumptions & Basis Table is missing key assumption '{key_drv}'."
                    )
            for drv_k, b_entry in ab.items():
                if b_entry.get("basis_type") == "thesis":
                    for tid in b_entry.get("thesis_ids", []):
                        if not re.search(rf"\b{re.escape(tid)}\b", sec8_tables_text):
                            errors.append(
                                f"Section 8 Model Assumptions & Basis Table must cite Thesis Pillar '{tid}' (linked to '{drv_k}')."
                            )

    # 3. Anti-slop prose lint
    for idx, line in enumerate(md_text.splitlines(), start=1):
        for rule_label, pat in BANNED_SLOP_PATTERNS:
            m = re.search(pat, line, flags=re.IGNORECASE)
            if m:
                warnings.append(f"Line {idx} [{rule_label}]: found '{m.group(0)}' -> rewrite plainly.")

    status = "PASS" if not errors else "FAIL"
    return {
        "status": status,
        "report_path": str(report_md_path),
        "valuation_summary_path": str(valuation_summary_path),
        "errors": errors,
        "warnings": warnings,
    }


def export_html(report_md_path: Path, out_html_path: Path) -> Path:
    md_text = report_md_path.read_text(encoding="utf-8")
    html_body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "sane_lists"])
    full_html = PRINT_CSS.format(title=report_md_path.stem, body=html_body)
    out_html_path.parent.mkdir(parents=True, exist_ok=True)
    out_html_path.write_text(full_html, encoding="utf-8")
    return out_html_path


def _register_pdf_fonts() -> tuple[str, str, str]:
    """Register Unicode TrueType fonts when present on the host; fall back cleanly to Helvetica/Courier."""
    candidates = [
        (
            "FBBody",
            Path("C:/Windows/Fonts/calibri.ttf"),
            Path("C:/Windows/Fonts/calibrib.ttf"),
            Path("C:/Windows/Fonts/calibrii.ttf"),
            Path("C:/Windows/Fonts/calibriz.ttf"),
            "FBMono",
            Path("C:/Windows/Fonts/consola.ttf"),
        ),
        (
            "FBBody",
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("C:/Windows/Fonts/arialbd.ttf"),
            Path("C:/Windows/Fonts/ariali.ttf"),
            Path("C:/Windows/Fonts/arialbi.ttf"),
            "FBMono",
            Path("C:/Windows/Fonts/cour.ttf"),
        ),
        (
            "FBBody",
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf"),
            "FBMono",
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
        ),
    ]
    for fam, reg, bold, ital, bi, mono_name, mono_p in candidates:
        if reg.exists() and bold.exists() and ital.exists() and bi.exists():
            try:
                pdfmetrics.registerFont(TTFont(fam, str(reg)))
                pdfmetrics.registerFont(TTFont(f"{fam}-Bold", str(bold)))
                pdfmetrics.registerFont(TTFont(f"{fam}-Italic", str(ital)))
                pdfmetrics.registerFont(TTFont(f"{fam}-BoldItalic", str(bi)))
                pdfmetrics.registerFontFamily(
                    fam,
                    normal=fam,
                    bold=f"{fam}-Bold",
                    italic=f"{fam}-Italic",
                    boldItalic=f"{fam}-BoldItalic",
                )
                mono_final = "Courier"
                if mono_p.exists():
                    pdfmetrics.registerFont(TTFont(mono_name, str(mono_p)))
                    mono_final = mono_name
                return fam, f"{fam}-Bold", mono_final
            except Exception:
                continue
    return "Helvetica", "Helvetica-Bold", "Courier"


def _clean_text(s: str, use_unicode_ttf: bool) -> str:
    for k, v in UNICODE_FALLBACK_MAP.items():
        if not use_unicode_ttf or k in ("\u2014", "\u00a0"):
            s = s.replace(k, v)
    if not use_unicode_ttf:
        s = s.encode("cp1252", errors="replace").decode("cp1252")
    return s


def _inline_rl_xml(node: Any, mono_font: str, use_unicode_ttf: bool) -> str:
    """Convert BeautifulSoup inline DOM nodes into safe ReportLab Paragraph XML."""
    if isinstance(node, NavigableString):
        return html.escape(_clean_text(str(node), use_unicode_ttf))
    if not isinstance(node, Tag):
        return ""
    tag = node.name.lower()
    if tag == "br":
        return "<br/>"
    inner = "".join(_inline_rl_xml(child, mono_font, use_unicode_ttf) for child in node.children)
    if tag in ("strong", "b"):
        return f"<b>{inner}</b>"
    if tag in ("em", "i"):
        return f"<i>{inner}</i>"
    if tag == "code":
        code_txt = html.escape(_clean_text(node.get_text(), use_unicode_ttf))
        return f'<font name="{mono_font}" size="8.3" color="#1B365D">{code_txt}</font>'
    if tag == "a":
        href = html.escape(node.get("href", ""), quote=True)
        if href and not href.startswith("#"):
            return f'<link href="{href}" color="#2B6CB0"><u>{inner}</u></link>'
        return inner
    return inner


def _is_numeric_col(col_texts: list[str]) -> bool:
    non_empty = [t.strip() for t in col_texts if t.strip() and t.strip().upper() not in ("N/A", "-")]
    if not non_empty:
        return False
    num_hits = 0
    for val in non_empty:
        cleaned = re.sub(r"(?i)\b(hkd|usd|rmb|cny|eur|gbp|jpy|bps)\b", "", val)
        cleaned = re.sub(r"(?i)(hk\$|us\$|[$€£¥,+%xX()*~\s/])", "", cleaned)
        cleaned = cleaned.replace("M", "").replace("B", "").replace("T", "")
        if re.fullmatch(r"-?\d+(\.\d+)?(-?\d+(\.\d+)?)?", cleaned):
            num_hits += 1
    return (num_hits / len(non_empty)) >= 0.6


def export_pdf(report_md_path: Path, out_pdf_path: Path, valuation_summary_path: Path) -> Path:
    """Render an institutional sell-side equity research PDF from audited Markdown + valuation_summary.json."""
    md_text = report_md_path.read_text(encoding="utf-8")
    val = json.loads(valuation_summary_path.read_text(encoding="utf-8"))

    body_font, bold_font, mono_font = _register_pdf_fonts()
    use_unicode_ttf = body_font != "Helvetica"

    navy = colors.HexColor("#1B365D")
    slate = colors.HexColor("#2C5282")
    dark_text = colors.HexColor("#1A202C")
    muted_text = colors.HexColor("#4A5568")
    border_grey = colors.HexColor("#CBD5E0")
    row_alt = colors.HexColor("#F8FAFC")
    callout_bg = colors.HexColor("#F0F4F8")

    rating_str = str(val.get("rating", "HOLD")).upper()
    badge_color = (
        colors.HexColor("#1E7E34")
        if rating_str == "BUY"
        else (colors.HexColor("#C53030") if rating_str == "SELL" else colors.HexColor("#B7791F"))
    )

    out_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(out_pdf_path),
        pagesize=letter,
        leftMargin=0.58 * inch,
        rightMargin=0.58 * inch,
        topMargin=0.68 * inch,
        bottomMargin=0.62 * inch,
        title=f"{val.get('ticker', '')} Institutional Equity Research Report",
        author="Finance Bro Equity Research",
    )
    avail_w = doc.width

    base_styles = getSampleStyleSheet()
    st_h1 = ParagraphStyle(
        "FB_H1",
        parent=base_styles["Heading1"],
        fontName=bold_font,
        fontSize=14.5,
        leading=18.5,
        textColor=navy,
        spaceBefore=8,
        spaceAfter=6,
    )
    st_h2 = ParagraphStyle(
        "FB_H2",
        parent=base_styles["Heading2"],
        fontName=bold_font,
        fontSize=11.8,
        leading=15.0,
        textColor=navy,
        spaceBefore=12,
        spaceAfter=3,
        keepWithNext=True,
    )
    st_h3 = ParagraphStyle(
        "FB_H3",
        parent=base_styles["Heading3"],
        fontName=bold_font,
        fontSize=10.2,
        leading=13.5,
        textColor=slate,
        spaceBefore=8,
        spaceAfter=3,
        keepWithNext=True,
    )
    st_body = ParagraphStyle(
        "FB_Body",
        parent=base_styles["Normal"],
        fontName=body_font,
        fontSize=9.3,
        leading=13.4,
        textColor=dark_text,
        spaceBefore=2,
        spaceAfter=5,
    )
    st_bullet = ParagraphStyle(
        "FB_Bullet",
        parent=st_body,
        leftIndent=14,
        firstLineIndent=0,
        bulletIndent=4,
        spaceBefore=1.5,
        spaceAfter=3.5,
    )
    st_quote = ParagraphStyle(
        "FB_Quote",
        parent=st_body,
        fontSize=9.1,
        leading=13.0,
        textColor=navy,
        spaceBefore=0,
        spaceAfter=0,
    )
    st_code = ParagraphStyle(
        "FB_Code",
        parent=base_styles["Code"],
        fontName=mono_font,
        fontSize=7.8,
        leading=10.5,
        textColor=dark_text,
        backColor=colors.HexColor("#EDF2F7"),
        leftIndent=6,
        rightIndent=6,
        spaceBefore=4,
        spaceAfter=6,
    )

    story: list[Any] = []

    # Institutional Page-1 Masthead Banner
    csym = _currency_symbol(str(val.get("currency", "USD")))
    ticker = str(val.get("ticker", "")).upper()
    comp_name = _clean_text(str(val.get("company_name", ticker)), use_unicode_ttf)
    tp = float(val.get("blended_target_price", 0.0))
    cp = float(val.get("current_price", 0.0))
    upside = float(val.get("implied_upside_pct", 0.0))
    val_date = str(val.get("valuation_date", ""))

    mast_left = Paragraph(
        f'<font size="8" color="#CBD5E0"><b>INSTITUTIONAL EQUITY RESEARCH  |  COVERAGE INITIATION</b></font><br/>'
        f'<font size="15" color="#FFFFFF"><b>{html.escape(comp_name)} ({html.escape(ticker)})</b></font><br/>'
        f'<font size="8.5" color="#E2E8F0">Valuation Date: {html.escape(val_date)}  |  Model: {html.escape(str(val.get("model_type", "standard_dcf")))}</font>',
        ParagraphStyle("MastL", fontName=body_font, leading=14.5),
    )
    mast_right = Paragraph(
        f'<font size="12" color="#FFFFFF"><b>RATING: {html.escape(rating_str)}</b></font><br/>'
        f'<font size="9.5" color="#FFFFFF"><b>Target: {html.escape(csym)}{tp:,.2f}</b> ({upside:+.2f}%)</font><br/>'
        f'<font size="8.5" color="#F7FAFC">Current Price: {html.escape(csym)}{cp:,.2f}</font>',
        ParagraphStyle("MastR", fontName=body_font, leading=13.5, alignment=TA_RIGHT),
    )
    mast_tbl = Table([[mast_left, mast_right]], colWidths=[avail_w * 0.67, avail_w * 0.33])
    mast_tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), navy),
                ("BACKGROUND", (1, 0), (1, 0), badge_color),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 11),
                ("RIGHTPADDING", (0, 0), (-1, -1), 11),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.append(mast_tbl)
    story.append(Spacer(1, 8))

    # Parse Markdown via HTML DOM (ensure blank line before list blocks for sane_lists)
    md_norm = re.sub(r"(?m)^([^\n#>*\-\d].*)\n(\s*(?:[*+-]|\d+\.)\s+)", r"\1\n\n\2", md_text)
    html_str = markdown.markdown(md_norm, extensions=["tables", "fenced_code", "sane_lists"])
    soup = BeautifulSoup(html_str, "html.parser")

    first_h1_skipped = False

    def _render_list(list_tag: Tag, ordered: bool, depth: int = 0) -> None:
        idx_num = 1
        for li in list_tag.find_all("li", recursive=False):
            # Separate nested lists inside <li>
            nested_lists = [c for c in li.children if isinstance(c, Tag) and c.name in ("ul", "ol")]
            inline_parts: list[str] = []
            for c in li.children:
                if isinstance(c, Tag) and c.name in ("ul", "ol"):
                    continue
                if isinstance(c, Tag) and c.name == "p":
                    inline_parts.append(
                        "".join(_inline_rl_xml(gc, mono_font, use_unicode_ttf) for gc in c.children)
                    )
                else:
                    inline_parts.append(_inline_rl_xml(c, mono_font, use_unicode_ttf))
            txt = re.sub(r"\s+", " ", "".join(inline_parts)).strip()
            if txt:
                st_item = ParagraphStyle(
                    f"FB_List_{depth}",
                    parent=st_bullet,
                    leftIndent=14 + depth * 12,
                    bulletIndent=3 + depth * 12,
                )
                bullet_tok = f"{idx_num}." if ordered else ("\u2022" if use_unicode_ttf else "-")
                story.append(Paragraph(txt, st_item, bulletText=bullet_tok))
                idx_num += 1
            for nl in nested_lists:
                _render_list(nl, nl.name == "ol", depth + 1)

    for elem in soup.children:
        if isinstance(elem, NavigableString):
            continue
        if not isinstance(elem, Tag):
            continue
        tname = elem.name.lower()

        if tname == "h1":
            if not first_h1_skipped:
                # Render subtitle line gently if H1 has extra context beyond ticker, else skip duplicate banner
                h1_txt = _inline_rl_xml(elem, mono_font, use_unicode_ttf).strip()
                first_h1_skipped = True
                if h1_txt:
                    story.append(Paragraph(h1_txt, st_h1))
            else:
                story.append(Paragraph(_inline_rl_xml(elem, mono_font, use_unicode_ttf), st_h1))

        elif tname == "h2":
            h2_xml = _inline_rl_xml(elem, mono_font, use_unicode_ttf)
            hr = HRFlowable(width="100%", thickness=1.0, color=navy, spaceBefore=0, spaceAfter=5)
            hr.keepWithNext = True
            story.append(Paragraph(h2_xml, st_h2))
            story.append(hr)

        elif tname in ("h3", "h4"):
            story.append(Paragraph(_inline_rl_xml(elem, mono_font, use_unicode_ttf), st_h3))

        elif tname == "p":
            pxml = _inline_rl_xml(elem, mono_font, use_unicode_ttf).strip()
            if pxml:
                story.append(Paragraph(pxml, st_body))

        elif tname in ("ul", "ol"):
            _render_list(elem, ordered=(tname == "ol"), depth=0)

        elif tname == "blockquote":
            q_parts: list[str] = []
            for child in elem.children:
                if isinstance(child, Tag) and child.name == "p":
                    q_parts.append(_inline_rl_xml(child, mono_font, use_unicode_ttf).strip())
                elif isinstance(child, Tag):
                    q_parts.append(_inline_rl_xml(child, mono_font, use_unicode_ttf).strip())
            q_xml = "<br/>".join(p for p in q_parts if p)
            if q_xml:
                qt = Table([[Paragraph(q_xml, st_quote)]], colWidths=[avail_w])
                qt.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, -1), callout_bg),
                            ("LINEBEFORE", (0, 0), (0, -1), 3.0, slate),
                            ("LEFTPADDING", (0, 0), (-1, -1), 10),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                            ("TOPPADDING", (0, 0), (-1, -1), 6),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                        ]
                    )
                )
                story.append(Spacer(1, 3))
                story.append(qt)
                story.append(Spacer(1, 5))

        elif tname == "pre":
            code_raw = _clean_text(elem.get_text(), use_unicode_ttf).rstrip("\n")
            if code_raw:
                story.append(Preformatted(code_raw, st_code))

        elif tname == "hr":
            story.append(HRFlowable(width="100%", thickness=0.6, color=border_grey, spaceBefore=5, spaceAfter=5))

        elif tname == "table":
            rows_raw: list[list[Tag]] = []
            for tr in elem.find_all("tr"):
                cells = tr.find_all(["th", "td"], recursive=False)
                if cells:
                    rows_raw.append(cells)
            if not rows_raw:
                continue

            n_cols = max(len(r) for r in rows_raw)
            # Determine font size dynamically by column count so wide financial tables never clip
            if n_cols <= 4:
                tbl_fs, tbl_lead, pad_h, pad_v = 8.4, 11.0, 6, 4.5
            elif n_cols <= 7:
                tbl_fs, tbl_lead, pad_h, pad_v = 7.7, 10.0, 4.5, 4.0
            else:
                tbl_fs, tbl_lead, pad_h, pad_v = 7.0, 9.2, 3.5, 3.5

            # Inspect plain text lengths & column alignments
            plain_grid: list[list[str]] = []
            for r in rows_raw:
                prow = [_clean_text(c.get_text(" ", strip=True), use_unicode_ttf) for c in r]
                while len(prow) < n_cols:
                    prow.append("")
                plain_grid.append(prow)

            col_align_right: list[bool] = []
            for c_idx in range(n_cols):
                if c_idx == 0:
                    col_align_right.append(False)
                    continue
                style_attr = rows_raw[0][c_idx].get("style", "") if c_idx < len(rows_raw[0]) else ""
                if "right" in style_attr.lower():
                    col_align_right.append(True)
                elif "left" in style_attr.lower():
                    col_align_right.append(False)
                else:
                    body_col = [plain_grid[r_i][c_idx] for r_i in range(1, len(plain_grid))]
                    col_align_right.append(_is_numeric_col(body_col))

            # Proportional column widths bounded sensibly
            col_weights: list[float] = []
            for c_idx in range(n_cols):
                max_chars = max((len(plain_grid[r_i][c_idx]) for r_i in range(len(plain_grid))), default=6)
                if c_idx == 0:
                    w = min(max(float(max_chars), 14.0), 38.0 if n_cols >= 7 else 46.0)
                else:
                    cap = 18.0 if col_align_right[c_idx] else 34.0
                    w = min(max(float(max_chars) * 1.08, 7.5), cap)
                col_weights.append(w)
            tot_w = sum(col_weights) or 1.0
            col_widths = [(w / tot_w) * avail_w for w in col_weights]

            st_th_l = ParagraphStyle(
                "FB_TH_L", fontName=bold_font, fontSize=tbl_fs, leading=tbl_lead, textColor=colors.white, alignment=TA_LEFT
            )
            st_th_r = ParagraphStyle(
                "FB_TH_R", fontName=bold_font, fontSize=tbl_fs, leading=tbl_lead, textColor=colors.white, alignment=TA_RIGHT
            )
            st_td_l = ParagraphStyle(
                "FB_TD_L", fontName=body_font, fontSize=tbl_fs, leading=tbl_lead, textColor=dark_text, alignment=TA_LEFT
            )
            st_td_r = ParagraphStyle(
                "FB_TD_R", fontName=body_font, fontSize=tbl_fs, leading=tbl_lead, textColor=dark_text, alignment=TA_RIGHT
            )

            rl_grid: list[list[Paragraph]] = []
            bold_row_indices: list[int] = []
            for r_i, r_cells in enumerate(rows_raw):
                is_hdr = r_i == 0 and all(c.name == "th" for c in r_cells)
                first_txt = plain_grid[r_i][0].lower()
                if not is_hdr and any(
                    k in first_txt for k in ("blended", "total", "our forecast", "unlevered fcf")
                ):
                    bold_row_indices.append(r_i)
                row_paras: list[Paragraph] = []
                for c_idx in range(n_cols):
                    if c_idx < len(r_cells):
                        c_xml = _inline_rl_xml(r_cells[c_idx], mono_font, use_unicode_ttf).strip()
                    else:
                        c_xml = ""
                    if is_hdr:
                        c_xml = re.sub(r"</?font[^>]*>", "", c_xml)
                        p_style = st_th_r if col_align_right[c_idx] else st_th_l
                    else:
                        p_style = st_td_r if col_align_right[c_idx] else st_td_l
                    row_paras.append(Paragraph(c_xml or "-", p_style))
                rl_grid.append(row_paras)

            t_cmds: list[tuple[Any, ...]] = [
                ("BACKGROUND", (0, 0), (-1, 0), navy),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), pad_h),
                ("RIGHTPADDING", (0, 0), (-1, -1), pad_h),
                ("TOPPADDING", (0, 0), (-1, -1), pad_v),
                ("BOTTOMPADDING", (0, 0), (-1, -1), pad_v),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
                ("LINEBELOW", (0, -1), (-1, -1), 1.0, navy),
            ]
            for r_i in range(1, len(rl_grid)):
                if r_i % 2 == 0:
                    t_cmds.append(("BACKGROUND", (0, r_i), (-1, r_i), row_alt))
            for b_i in bold_row_indices:
                t_cmds.append(("BACKGROUND", (0, b_i), (-1, b_i), colors.HexColor("#EDF2F7")))
                t_cmds.append(("LINEABOVE", (0, b_i), (-1, b_i), 0.7, navy))

            pdf_tbl = Table(rl_grid, colWidths=col_widths, repeatRows=1, spaceBefore=4, spaceAfter=7)
            pdf_tbl.setStyle(TableStyle(t_cmds))
            story.append(pdf_tbl)

    def _draw_chrome(canvas: Any, doc_obj: Any) -> None:
        canvas.saveState()
        page_num = canvas.getPageNumber()
        y_bot = 0.40 * inch
        canvas.setStrokeColor(border_grey)
        canvas.setLineWidth(0.5)
        canvas.line(doc_obj.leftMargin, y_bot + 10, letter[0] - doc_obj.rightMargin, y_bot + 10)
        canvas.setFont(body_font, 7.5)
        canvas.setFillColor(muted_text)
        canvas.drawString(
            doc_obj.leftMargin,
            y_bot,
            f"{comp_name} ({ticker})  |  Primary-Source Filing & Live-Formula Valuation Coverage",
        )
        canvas.drawRightString(letter[0] - doc_obj.rightMargin, y_bot, f"Page {page_num}")

        if page_num > 1:
            y_top = letter[1] - 0.46 * inch
            canvas.setStrokeColor(navy)
            canvas.setLineWidth(0.6)
            canvas.line(doc_obj.leftMargin, y_top - 4, letter[0] - doc_obj.rightMargin, y_top - 4)
            canvas.setFont(bold_font, 8.0)
            canvas.setFillColor(navy)
            canvas.drawString(doc_obj.leftMargin, y_top, f"{comp_name} ({ticker}) - Initiation Report")
            canvas.setFont(body_font, 8.0)
            canvas.setFillColor(muted_text)
            canvas.drawRightString(
                letter[0] - doc_obj.rightMargin,
                y_top,
                f"Rating: {rating_str}  |  Target: {csym}{tp:,.2f} ({upside:+.2f}%)",
            )
        canvas.restoreState()

    doc.build(story, onFirstPage=_draw_chrome, onLaterPages=_draw_chrome)
    return out_pdf_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit equity research report vs Excel valuation summary and export PDF")
    parser.add_argument("report_md", help="Path to Markdown report draft (e.g. memory/<TICKER>/report_draft.md)")
    parser.add_argument("valuation_summary", help="Path to memory/<TICKER>/valuation_summary.json")
    parser.add_argument("--strict-slop", action="store_true", help="Fail exit code on prose warnings too")
    parser.add_argument("--export-pdf", help="Path to export final institutional PDF report (Output/reports/<TICKER>_report.pdf)")
    parser.add_argument("--export-html", help="Optional path to export print-ready HTML report")
    parser.add_argument("--out-audit-json", help="Optional path to save audit JSON receipt")
    args = parser.parse_args()

    rep_p = Path(args.report_md)
    val_p = Path(args.valuation_summary)
    if not rep_p.exists() or not val_p.exists():
        print(f"Missing input file(s): report={rep_p.exists()}, summary={val_p.exists()}", file=sys.stderr)
        return 1

    res = audit_report(rep_p, val_p)
    failed = bool(res["errors"] or (args.strict_slop and res["warnings"]))

    if not failed:
        if args.export_pdf:
            pdf_p = export_pdf(rep_p, Path(args.export_pdf), val_p)
            res["exported_pdf"] = str(pdf_p)
        if args.export_html:
            html_p = export_html(rep_p, Path(args.export_html))
            res["exported_html"] = str(html_p)

    if args.out_audit_json:
        aj = Path(args.out_audit_json)
        aj.parent.mkdir(parents=True, exist_ok=True)
        aj.write_text(json.dumps(res, indent=2), encoding="utf-8")

    print(json.dumps(res, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

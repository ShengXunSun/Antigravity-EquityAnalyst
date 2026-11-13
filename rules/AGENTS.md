# Finance Bro Equity Research Conventions

When running any Finance Bro equity research skill (`ips-setup`, `equity-screener`, `equity-analyst`, `research-report`, or `equity-research-pipeline`):

1. **Script Resolution:** Execute bundled PEP 723 Python scripts with `uv run <scripts_dir>/<script>.py` (where `<scripts_dir>` is `./src` if present in the active workspace, otherwise the `scripts/` folder beside `skills/` inside this package).
2. **Artifact Paths in Active Workspace:**
   - `memory/client_ips.md` — validated hybrid YAML + Markdown Investment Policy Statement
   - `memory/<TICKER>/` — downloaded SEC filings, XBRL facts JSON, consensus/Reverse DCF JSON, peer comps JSON, `analyst_dossier.md`, `valuation_spec.json`, `valuation_summary.json`, `report_draft.md`, and `report_audit.json`
   - `Output/models/<TICKER>_valuation.xlsx` — 100% live-formula 5-year Excel valuation workbook
   - `Output/reports/<TICKER>_report.pdf` — numerically audited institutional PDF coverage report
3. **Integrity Rules:** Ground historical numbers in SEC EDGAR (`edgar_client.py`), never hardcode calculated outputs in Excel cells, and keep `audit_report.py --strict-slop` green before final delivery.

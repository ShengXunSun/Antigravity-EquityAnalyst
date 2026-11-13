#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Append-only TSV decision trail logger compatible with show-me-your-work."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

HEADER = "ts\tphase\tdecision\twhy\tevidence\tresult\n"
FORMULA_PREFIXES = ("=", "+", "-", "@")


def sanitize_cell(value: str) -> str:
    cleaned = " ".join(value.replace("\t", " ").replace("\r", " ").replace("\n", " ").split())
    if cleaned.startswith(FORMULA_PREFIXES):
        cleaned = "'" + cleaned
    return cleaned


def append_decision(
    logfile: str | Path,
    phase: str,
    decision: str,
    why: str,
    evidence: str,
    result: str,
) -> Path:
    path = Path(logfile)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size == 0:
        path.write_text(HEADER, encoding="utf-8")

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    row = "\t".join(
        [
            ts,
            sanitize_cell(phase),
            sanitize_cell(decision),
            sanitize_cell(why),
            sanitize_cell(evidence),
            sanitize_cell(result),
        ]
    )
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(row + "\n")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Append a decision row to a TSV audit trail.")
    parser.add_argument("logfile", help="Path to decisions.tsv (e.g. memory/decisions.tsv)")
    parser.add_argument("phase", help="Pipeline phase (e.g. ips, screen, analyst, valuation, report)")
    parser.add_argument("decision", help="What was chosen or done (one line)")
    parser.add_argument("why", help="Plain-language rationale")
    parser.add_argument("evidence", help="File path, filing accession, or script output pointer")
    parser.add_argument("result", help="Outcome state (e.g. '4 finalists', 'audit green', 'rejected')")
    args = parser.parse_args()

    out = append_decision(
        args.logfile, args.phase, args.decision, args.why, args.evidence, args.result
    )
    print(f"Logged decision to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

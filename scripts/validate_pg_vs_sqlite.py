"""
Compare analytics outputs: SQLite (baseline) vs PostgreSQL (adapter).

Run BEFORE enabling USE_POSTGRES=true in production.
Does not modify the database.

Usage (repo root):
  set PYTHONPATH=phase_2_dashboard
  python scripts/validate_pg_vs_sqlite.py
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
_PKG = _ROOT / "phase_2_dashboard"
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))


def _reload_settings() -> None:
    from core.config import get_settings

    get_settings.cache_clear()


def _run_backend(use_postgres: bool) -> dict:
    os.environ["USE_POSTGRES"] = "true" if use_postgres else "false"
    _reload_settings()

    from data_loader import (
        kpi_bundle,
        load_dashboard_frames,
        preset_range,
        returns_vs_sales_by_store,
        revenue_by_store,
    )

    inv, lines = load_dashboard_frames()
    start, end = preset_range("1 თვე")
    kpi = kpi_bundle(inv, lines, start, end)
    rev_store = revenue_by_store(inv, start, end)
    ret_store = returns_vs_sales_by_store(inv, lines, start, end)
    return {
        "inv_rows": len(inv),
        "line_rows": len(lines),
        "inv_cols": set(inv.columns),
        "line_cols": set(lines.columns),
        "kpi": kpi,
        "rev_store_sum": float(rev_store["revenue_gel"].sum()) if not rev_store.empty else 0.0,
        "ret_sales_sum": float(ret_store["sales_gel"].sum()) if not ret_store.empty else 0.0,
        "ret_returns_sum": float(ret_store["returns_gel"].sum()) if not ret_store.empty else 0.0,
    }


def _compare_float(a: float, b: float, tol: float, label: str, errors: list[str]) -> None:
    if abs(a - b) > tol:
        errors.append(f"{label}: sqlite={a} postgres={b} (tol={tol})")


def main() -> int:
    parser = argparse.ArgumentParser(description="SQLite vs PostgreSQL analytics parity check")
    parser.add_argument("--tolerance", type=float, default=0.01, help="GEL tolerance for KPI floats")
    parser.add_argument("--skip-row-compare", action="store_true")
    args = parser.parse_args()

    errors: list[str] = []

    try:
        sqlite = _run_backend(False)
    except Exception as exc:
        print(f"FAIL: SQLite baseline: {exc}")
        return 1

    try:
        pg = _run_backend(True)
    except Exception as exc:
        print(f"FAIL: PostgreSQL via adapter: {exc}")
        print("Ensure DATABASE_URL, migrations, and migrate_sqlite_to_pg.py completed.")
        return 1

    if not args.skip_row_compare:
        if sqlite["inv_rows"] != pg["inv_rows"]:
            errors.append(f"invoice rows: sqlite={sqlite['inv_rows']} pg={pg['inv_rows']}")
        if sqlite["line_rows"] != pg["line_rows"]:
            errors.append(f"line_item rows: sqlite={sqlite['line_rows']} pg={pg['line_rows']}")
        if sqlite["inv_cols"] != pg["inv_cols"]:
            errors.append(
                f"invoice columns differ: only_sqlite={sqlite['inv_cols'] - pg['inv_cols']} "
                f"only_pg={pg['inv_cols'] - sqlite['inv_cols']}"
            )
        if sqlite["line_cols"] != pg["line_cols"]:
            errors.append(
                f"line columns differ: only_sqlite={sqlite['line_cols'] - pg['line_cols']} "
                f"only_pg={pg['line_cols'] - sqlite['line_cols']}"
            )

    for key in ("total_revenue_gel", "total_returns_gel", "returns_pct"):
        _compare_float(
            float(sqlite["kpi"][key]),
            float(pg["kpi"][key]),
            args.tolerance,
            f"kpi.{key}",
            errors,
        )
    if sqlite["kpi"]["n_stores"] != pg["kpi"]["n_stores"]:
        errors.append(
            f"kpi.n_stores: sqlite={sqlite['kpi']['n_stores']} pg={pg['kpi']['n_stores']}"
        )

    _compare_float(sqlite["rev_store_sum"], pg["rev_store_sum"], args.tolerance, "revenue_by_store.sum", errors)
    _compare_float(sqlite["ret_sales_sum"], pg["ret_sales_sum"], args.tolerance, "returns_vs_sales.sales", errors)
    _compare_float(sqlite["ret_returns_sum"], pg["ret_returns_sum"], args.tolerance, "returns_vs_sales.returns", errors)

    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("VALIDATION PASSED — SQLite and PostgreSQL outputs match within tolerance.")
    print(f"  invoices={sqlite['inv_rows']} lines={sqlite['line_rows']}")
    print(f"  kpi (1 month): {sqlite['kpi']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

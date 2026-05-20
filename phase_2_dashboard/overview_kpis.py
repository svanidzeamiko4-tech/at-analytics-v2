"""
ზედა KPI ზოლი — 1 დიდი + 3 ბარათი, რეალური DB მონაცემები.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from components.stat_card import render_kpi_overview_row
from data_loader import kpi_bundle, returns_vs_sales_by_store, top_products_by_quantity


def _truncate(s: str, n: int = 40) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def render_overview_kpi_strip(
    invoices: pd.DataFrame,
    lines: pd.DataFrame,
    d_start: date,
    d_end: date,
) -> None:
    kp = kpi_bundle(invoices, lines, d_start, d_end)
    rs = returns_vs_sales_by_store(invoices, lines, d_start, d_end)

    if rs.empty:
        sales_vol = 0.0
        rr_line = 0.0
    else:
        sales_vol = float(pd.to_numeric(rs["sales_gel"], errors="coerce").fillna(0.0).sum())
        ret_sum = float(pd.to_numeric(rs["returns_gel"], errors="coerce").fillna(0.0).sum())
        rr_line = (ret_sum / sales_vol * 100.0) if sales_vol > 1e-9 else 0.0

    n_stores = int(kp.get("n_stores", 0) or 0)

    top_df = top_products_by_quantity(invoices, lines, d_start, d_end, top_n=1)
    if top_df.empty:
        top_label = "—"
        top_change = None
    else:
        row = top_df.iloc[0]
        top_label = _truncate(str(row.get("product_label", "")), 44)
        top_change = f"რაოდენობა: {float(row.get('quantity', 0)):,.0f}"

    if rr_line <= 10.0:
        rr_status, rr_change = "success", "დაბალი რისკი"
    elif rr_line <= 22.0:
        rr_status, rr_change = "warning", "საშუალო"
    else:
        rr_status, rr_change = "danger", "⚠️ მაღალი რისკი"

    render_kpi_overview_row(
        main={
            "title": "ჯამური გაყიდვები",
            "value": f"{sales_vol:,.2f} GEL",
            "change": "Sales Volume (არჩეული პერიოდი)",
            "status": "neutral",
        },
        secondary=[
            {
                "title": "აქტიური მაღაზიები",
                "value": str(n_stores),
                "change": "Partner Stores",
                "status": "neutral",
            },
            {
                "title": "დაბრუნების კოეფიციენტი",
                "value": f"{rr_line:.2f}%",
                "change": rr_change,
                "status": rr_status,
            },
            {
                "title": "ტოპ პროდუქტი",
                "value": top_label,
                "change": top_change,
                "status": "highlight" if top_change else "neutral",
            },
        ],
    )

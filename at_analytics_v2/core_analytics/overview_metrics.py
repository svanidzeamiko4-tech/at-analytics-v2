"""
ზედა KPI ზოლი: გაყიდვების ჯამი (ხაზი), პარტნიორი მაღაზიები, return rate ინდიკატორი, ტოპ პროდუქტი.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from .data_bridge import ensure_phase2_import_path


def _truncate(s: str, n: int = 40) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def render_header_metrics(
    invoices: pd.DataFrame,
    lines: pd.DataFrame,
    d_start: date,
    d_end: date,
) -> None:
    ensure_phase2_import_path()
    import data_loader as dl  # noqa: E402

    kp = dl.kpi_bundle(invoices, lines, d_start, d_end)
    rs = dl.returns_vs_sales_by_store(invoices, lines, d_start, d_end)

    if rs.empty:
        sales_vol = 0.0
        rr_line = 0.0
    else:
        sales_vol = float(pd.to_numeric(rs["sales_gel"], errors="coerce").fillna(0.0).sum())
        ret_sum = float(pd.to_numeric(rs["returns_gel"], errors="coerce").fillna(0.0).sum())
        rr_line = (ret_sum / sales_vol * 100.0) if sales_vol > 1e-9 else 0.0

    n_stores = int(kp.get("n_stores", 0) or 0)

    top_df = dl.top_products_by_quantity(invoices, lines, d_start, d_end, top_n=1)
    if top_df.empty:
        top_label = "—"
        top_delta = None
    else:
        row = top_df.iloc[0]
        top_label = _truncate(str(row.get("product_label", "")), 44)
        top_delta = f"რაოდენობა: {float(row.get('quantity', 0)):,.0f}"

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric(
            "ჯამური გაყიდვები (Sales Volume)",
            f"{sales_vol:,.2f} GEL",
            help="ხაზის დონეზე დადებითი გაყიდვების ჯამი არჩეულ პერიოდში",
        )
    with c2:
        st.metric(
            "აქტიური მაღაზიები (Partner Stores)",
            str(n_stores),
            help="უნიკალური მაღაზია/ფილიალი ინვოისებში (პერიოდი)",
        )
    with c3:
        if rr_line <= 10.0:
            delta_txt = "დაბალი რისკი"
            dc: str = "normal"
        elif rr_line <= 22.0:
            delta_txt = "საშუალო"
            dc = "off"
        else:
            delta_txt = "მაღალი რისკი"
            dc = "inverse"
        st.metric(
            "დაბრუნების კოეფიციენტი (Return Rate %)",
            f"{rr_line:.2f}%",
            delta=delta_txt,
            delta_color=dc,
            help="(ჯამური დაბრუნებები / ჯამური გაყიდვები ხაზზე) × 100",
        )
    with c4:
        st.metric(
            "ყველაზე მოთხოვნადი პროდუქტი (Top Performer)",
            top_label,
            delta=top_delta,
            help="რაოდენობით #1 პროდუქტი (მაღაზია · SKU)",
        )

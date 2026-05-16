"""
ზედა KPI ზოლი (4 მეტრიკა) — იგივე ლოგიკა, რაც v2-ში; გამოიყენება ``phase_2_dashboard/app.py``.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from data_loader import kpi_bundle, returns_vs_sales_by_store, top_products_by_quantity


def _truncate(s: str, n: int = 40) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


_OVERVIEW_METRIC_CSS = """
<style>
    [data-testid="stMetric"] {
        background-color: #1e293b;
        border: 1px solid rgba(255,255,255,0.1);
        padding: 15px;
        border-radius: 10px;
        color: #ffffff;
    }
    [data-testid="stMetricLabel"] {
        color: #94a3b8 !important;
    }
    [data-testid="stMetricValue"] {
        color: #f8fafc !important;
    }
    [data-testid="stMetricDelta"] {
        color: #cbd5e1 !important;
    }
</style>
"""


def render_overview_kpi_strip(
    invoices: pd.DataFrame,
    lines: pd.DataFrame,
    d_start: date,
    d_end: date,
) -> None:
    st.markdown(_OVERVIEW_METRIC_CSS, unsafe_allow_html=True)
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
        kw: dict = {
            "label": "ყველაზე მოთხოვნადი პროდუქტი (Top Performer)",
            "value": top_label,
            "help": "რაოდენობით #1 პროდუქტი (მაღაზია · SKU)",
        }
        if top_delta is not None:
            kw["delta"] = top_delta
        st.metric(**kw)

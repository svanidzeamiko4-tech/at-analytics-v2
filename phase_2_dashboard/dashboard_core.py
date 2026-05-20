"""
Core dashboard rendering logic — imported by manager and distributor views.
No imports from app.py.
"""

from __future__ import annotations

import html
from datetime import date

import pandas as pd
import sqlite3
import streamlit as st

from ai_chat import render_floating_ai_chat
from ai_recommendations import render_ai_main_strip
from charts.product_chart import top_products_chart
from charts.sales_chart import sales_returns_area, sparkline
from charts.store_charts import sales_returns_bar, store_donut
from dashboard_layout import (
    apply_css,
    floating_chat_js,
    init_sidebar_dates,
    render_brand_header,
)
from data_loader import (
    all_products_by_quantity_share,
    connect_readonly,
    daily_revenue_series,
    daily_sales_returns_series,
    filter_by_date_range,
    kpi_bundle,
    load_dashboard_frames,
    period_calendar_days,
    preset_range,
    resolve_db_path,
    restock_recommendations_by_store,
    returns_vs_sales_by_store,
    store_share_with_returns_pct,
)
from overview_kpis import render_overview_kpi_strip
from store_efficiency_panel import render_store_efficiency_section
from ui_theme import (
    BORDER,
    CARD,
    EMERALD,
    GEO,
    MUTED,
    NEON_BLUE,
    PLOTLY_STREAMLIT_CONFIG,
    PRIMARY,
    RADIUS,
    SUCCESS,
)


def _filter_frames(
    inv: pd.DataFrame,
    lines: pd.DataFrame,
    allowed_store_ids: list[int] | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if allowed_store_ids is None:
        return inv, lines
    if not allowed_store_ids:
        return inv.iloc[0:0].copy(), lines.iloc[0:0].copy()
    inv_f = inv[inv["store_id"].isin(allowed_store_ids)].copy()
    if inv_f.empty:
        return inv_f, lines.iloc[0:0].copy()
    if "store_id" in lines.columns:
        lines_f = lines[lines["store_id"].isin(allowed_store_ids)].copy()
    else:
        lines_f = lines[lines["invoice_id"].isin(inv_f["invoice_id"])].copy()
    return inv_f, lines_f


def render_dashboard(
    inv: pd.DataFrame,
    lines: pd.DataFrame,
    d_start: date,
    d_end: date,
    allowed_store_ids: list[int] | None = None,
) -> None:
    """
    Render main dashboard content (KPIs, charts); restock cards in sidebar.
    ``allowed_store_ids=None`` → all stores; else filter to listed ids.
    """
    inv, lines = _filter_frames(inv, lines, allowed_store_ids)

    with st.container(border=True):
        st.markdown("##### სწრაფი მიმოხილვა")
        render_overview_kpi_strip(inv, lines, d_start, d_end)

    with st.container(border=True):
        st.markdown("##### მაღაზიები — Return Rate")
        render_store_efficiency_section(inv, lines, d_start, d_end)

    kpis = kpi_bundle(inv, lines, d_start, d_end)
    days_n = period_calendar_days(d_start, d_end)
    daily = daily_revenue_series(inv, d_start, d_end)
    daily_sr = daily_sales_returns_series(inv, lines, d_start, d_end)
    net = kpis["total_revenue_gel"] - kpis["total_returns_gel"]

    with st.container(border=True):
        st.markdown(f"##### {GEO['hero_title']}")
        h1, h2, h3 = st.columns((1.15, 1.15, 1.4))
        with h1:
            st.markdown(
                f'<p class="dash-hero-sub">{GEO["total_sales"]} (GEL, ინვოისი)</p>'
                f'<p class="dash-hero-num" style="color:{NEON_BLUE}">{kpis["total_revenue_gel"]:,.2f}</p>',
                unsafe_allow_html=True,
            )
        with h2:
            st.markdown(
                f'<p class="dash-hero-sub">{GEO["total_returns"]}</p>'
                f'<p class="dash-hero-num" style="color:{EMERALD}">{kpis["total_returns_gel"]:,.2f}</p>'
                f'<p class="dash-hero-sub">({kpis["returns_pct"]:.2f}% {GEO["returns_share_note"]})</p>',
                unsafe_allow_html=True,
            )
        with h3:
            st.caption(GEO["spark_caption"])
            st.plotly_chart(
                sparkline(daily),
                use_container_width=True,
                config=PLOTLY_STREAMLIT_CONFIG,
                key="spark_rev",
            )
        st.caption(GEO["hero_area_caption"])
        st.plotly_chart(
            sales_returns_area(daily_sr),
            use_container_width=True,
            config=PLOTLY_STREAMLIT_CONFIG,
            key="hero_area_sr",
        )

    k1, k2, k3 = st.columns(3)
    with k1:
        st.metric(
            GEO["net_revenue"],
            f"{net:,.2f} GEL",
            delta=f"{kpis['returns_pct']:.1f}% {GEO['delta_returns_vs_sales']}",
            delta_color="inverse",
        )
    with k2:
        st.metric(
            GEO["active_stores"],
            str(kpis["n_stores"]),
            help="უნიკალური მაღაზია/ფილიალი არჩეულ პერიოდში",
        )
    with k3:
        st.metric(GEO["calendar_days"], str(days_n), delta=f"{d_start} → {d_end}")

    store_df = store_share_with_returns_pct(inv, lines, d_start, d_end)
    rsr = returns_vs_sales_by_store(inv, lines, d_start, d_end)
    with st.container(border=True):
        st.plotly_chart(
            store_donut(store_df),
            use_container_width=True,
            config=PLOTLY_STREAMLIT_CONFIG,
            key="donut",
        )
    with st.container(border=True):
        st.plotly_chart(
            sales_returns_bar(rsr),
            use_container_width=True,
            config=PLOTLY_STREAMLIT_CONFIG,
            key="bars_sr",
        )

    with st.container(border=True):
        prod_df = all_products_by_quantity_share(inv, lines, d_start, d_end)
        st.plotly_chart(
            top_products_chart(prod_df, top_n=15),
            use_container_width=True,
            config=PLOTLY_STREAMLIT_CONFIG,
            key="products_all",
        )

    rec = restock_recommendations_by_store(inv, d_start, d_end)
    if not rec.empty:
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 📦 მარაგების შევსება")
        st.sidebar.caption("რეკომენდებული · 1–2 დღე")
        for _, row in rec.iterrows():
            sname = str(row["store_name"])
            display = html.escape(sname[:25] + "…" if len(sname) > 25 else sname)
            st.sidebar.markdown(
                f"""
            <div style="
                background: {CARD};
                border: 1px solid {BORDER};
                border-radius: {RADIUS};
                padding: 14px 16px;
                margin-bottom: 10px;
            ">
                <div style="color:{PRIMARY};font-size:0.68rem;
                    text-transform:uppercase;letter-spacing:0.08em;
                    margin-bottom:4px;">შევსება · 1–2 დღე</div>
                <div style="color:#E5E7EB;font-size:0.88rem;
                    font-weight:600;margin-bottom:6px;">{display}</div>
                <div style="color:{SUCCESS};font-size:1.1rem;
                    font-weight:700;">{row['recommended_restock_gel']:,.2f} GEL</div>
                <div style="color:{MUTED};font-size:0.72rem;margin-top:4px;">
                    საშ: {row['avg_daily_revenue_gel']:,.2f} ·
                    სიზ: {int(row['confidence_pct'])}%
                </div>
            </div>
            """,
                unsafe_allow_html=True,
            )



def render_dashboard_page(
    *,
    allowed_store_ids: list[int] | None = None,
    subtitle: str | None = None,
    show_ai_chat: bool = True,
) -> None:
    """Full page: shell (header, DB, sidebar) + :func:`render_dashboard`."""
    apply_css()
    floating_chat_js()
    render_brand_header()
    if subtitle:
        st.caption(subtitle)
    render_ai_main_strip()

    db_path = resolve_db_path()
    if not db_path.is_file():
        st.error(f"{GEO['no_db']}: `{db_path}`")
        st.stop()

    try:
        with connect_readonly(db_path) as probe:
            probe.execute("SELECT 1")
    except sqlite3.Error as exc:
        st.error(f"{GEO['db_open_err']}: {exc}")
        st.stop()

    inv, lines = load_dashboard_frames(db_path)
    inv, lines = _filter_frames(inv, lines, allowed_store_ids)
    if allowed_store_ids is not None and inv.empty:
        st.warning("თქვენს ანგარიშზე მიბმული მაღაზიების მონაცემები ამ პერიოდში არ მოიძებნა.")
        return

    today = date.today()
    init_sidebar_dates(today)

    st.sidebar.markdown(f"### {GEO['time_range']}")
    presets_geo = ["7 დღე", "15 დღე", "1 თვე", "6 თვე", "1 წელი"]
    for i, label in enumerate(presets_geo):
        if st.sidebar.button(label, use_container_width=True, key=f"pre_{i}"):
            st.session_state["preset"] = label
            st.session_state["d_start"], st.session_state["d_end"] = preset_range(
                label, today
            )
            st.session_state["cust_start"] = st.session_state["d_start"]
            st.session_state["cust_end"] = st.session_state["d_end"]
            st.rerun()

    st.sidebar.markdown(f"**{GEO['custom_dates']}**")
    st.sidebar.date_input(GEO["start"], key="cust_start")
    st.sidebar.date_input(GEO["end"], key="cust_end")
    ca = st.session_state["cust_start"]
    cb = st.session_state["cust_end"]
    if ca <= cb:
        st.session_state["d_start"], st.session_state["d_end"] = ca, cb
    else:
        st.sidebar.caption(GEO["invalid_range"])

    d_start, d_end = st.session_state["d_start"], st.session_state["d_end"]
    st.sidebar.caption(f"**{GEO['active_range']}:** {d_start} → {d_end}")

    inv_f = filter_by_date_range(inv, "effective_date", d_start, d_end)
    n_inv = len(inv_f)
    n_lines = (
        len(lines[lines["invoice_id"].isin(inv_f["invoice_id"])]) if n_inv else 0
    )
    st.sidebar.metric(GEO["invoices"], n_inv)
    st.sidebar.metric(GEO["line_items"], n_lines)
    st.sidebar.caption(f"{GEO['db_file']}: `{db_path.name}`")

    render_dashboard(inv, lines, d_start, d_end, allowed_store_ids=None)

    if show_ai_chat:
        render_floating_ai_chat()

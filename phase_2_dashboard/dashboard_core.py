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
from charts.product_chart import top_products_chart
from charts.sales_chart import sales_returns_area, sparkline
from charts.store_charts import sales_returns_bar, store_donut
from components.sidebar_shell import render_sidebar_filters
from dashboard_layout import (
    floating_chat_js,
    init_sidebar_dates,
    mobile_drawer_js,
)
from ui_shell import (
    apply_theme_css,
    init_app_state,
    render_ai_box,
    render_app_header,
    render_sidebar_navigation,
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
    PRIMARY,
    RADIUS,
    SUCCESS,
    is_dark_mode,
    themed_plotly_chart,
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


def render_restock_recommendations_section(
    inv: pd.DataFrame,
    d_start: date,
    d_end: date,
) -> None:
    """Restock cards for main content (not sidebar)."""
    rec = restock_recommendations_by_store(inv, d_start, d_end)
    st.markdown(f"### 📦 {GEO['restock_heading']}")
    st.caption(GEO['restock_sub'])
    if rec.empty:
        st.info(GEO["no_data"])
        return

    is_dark = is_dark_mode()
    card_bg = CARD if is_dark else "#ffffff"
    text_main = "#E5E7EB" if is_dark else "#0f172a"
    text_muted = MUTED if is_dark else "#64748b"
    border = BORDER if is_dark else "#e2e8f0"

    rows = list(rec.iterrows())
    for row_start in range(0, len(rows), 3):
        cols = st.columns(3)
        for col_idx, col in enumerate(cols):
            item_idx = row_start + col_idx
            if item_idx >= len(rows):
                break
            _, row = rows[item_idx]
            sname = str(row["store_name"])
            display = html.escape(sname[:28] + "…" if len(sname) > 28 else sname)
            with col:
                st.markdown(
                    f'<div class="dashboard-card" style="background:{card_bg};'
                    f"border:1px solid {border};border-radius:{RADIUS};"
                    f'padding:16px 18px;margin-bottom:12px;">'
                    f'<div style="color:{PRIMARY};font-size:0.68rem;text-transform:uppercase;'
                    f'letter-spacing:0.08em;margin-bottom:4px;">'
                    f"{GEO['restock_card_title']}</div>"
                    f'<div style="color:{text_main};font-size:0.9rem;font-weight:600;'
                    f'margin-bottom:8px;">{display}</div>'
                    f'<div style="color:{SUCCESS};font-size:1.15rem;font-weight:700;">'
                    f"{row['recommended_restock_gel']:,.2f} GEL</div>"
                    f'<div style="color:{text_muted};font-size:0.75rem;margin-top:6px;">'
                    f"{GEO['restock_avg']}: {row['avg_daily_revenue_gel']:,.2f} · "
                    f"{GEO['restock_conf']}: {int(row['confidence_pct'])}%</div></div>",
                    unsafe_allow_html=True,
                )


def render_dashboard(
    inv: pd.DataFrame,
    lines: pd.DataFrame,
    d_start: date,
    d_end: date,
    allowed_store_ids: list[int] | None = None,
) -> None:
    """
    Render main dashboard content (KPIs, charts). Restock → ``მარაგები`` page.
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
            themed_plotly_chart(sparkline(daily), key="spark_rev")
        st.caption(GEO["hero_area_caption"])
        themed_plotly_chart(sales_returns_area(daily_sr), key="hero_area_sr")

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
    st.markdown('<div class="chart-grid-2">', unsafe_allow_html=True)
    ch1, ch2 = st.columns(2)
    with ch1:
        st.markdown('<div class="chart-panel">', unsafe_allow_html=True)
        themed_plotly_chart(store_donut(store_df), key="donut")
        st.markdown("</div>", unsafe_allow_html=True)
    with ch2:
        st.markdown('<div class="chart-panel">', unsafe_allow_html=True)
        themed_plotly_chart(sales_returns_bar(rsr), key="bars_sr")
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    with st.container(border=True):
        prod_df = all_products_by_quantity_share(inv, lines, d_start, d_end)
        themed_plotly_chart(top_products_chart(prod_df, top_n=15), key="products_all")


def prepare_dashboard_data(
    allowed_store_ids: list[int] | None,
    *,
    sidebar_nav: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, date, date] | None:
    """Load DB, sidebar filters; return frames + active date range."""
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
        return None

    today = date.today()
    init_sidebar_dates(today)
    if sidebar_nav:
        render_sidebar_navigation()
    render_sidebar_filters(today)

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
    return inv, lines, d_start, d_end


def render_dashboard_shell(role_hint: str | None = None) -> None:
    """Header, theme CSS, mobile drawer, AI strip."""
    init_app_state()
    apply_theme_css()
    floating_chat_js()
    mobile_drawer_js()
    render_app_header(role_hint)
    render_ai_box()


def render_dashboard_page(
    *,
    allowed_store_ids: list[int] | None = None,
    subtitle: str | None = None,
    show_ai_chat: bool = True,
    sidebar_nav: bool = False,
) -> None:
    """Full page: shell + :func:`render_dashboard`."""
    render_dashboard_shell(subtitle)
    data = prepare_dashboard_data(allowed_store_ids, sidebar_nav=sidebar_nav)
    if data is None:
        return
    inv, lines, d_start, d_end = data
    render_dashboard(inv, lines, d_start, d_end, allowed_store_ids=None)
    if show_ai_chat:
        render_floating_ai_chat()

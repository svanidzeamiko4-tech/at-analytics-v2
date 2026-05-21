"""Manager dashboard — full network + page navigation."""

from __future__ import annotations

import streamlit as st

from charts.sales_chart import sales_returns_area
from charts.store_charts import sales_returns_bar, store_donut
from dashboard_core import (
    prepare_dashboard_data,
    render_dashboard,
    render_dashboard_shell,
    render_floating_ai_chat,
    render_restock_recommendations_section,
)
from data_loader import (
    daily_sales_returns_series,
    returns_vs_sales_by_store,
    store_share_with_returns_pct,
)
from pages.admin_panel import render as render_admin
from pages.order_planning import render as render_order_planning
from store_efficiency_panel import render_store_efficiency_section
from ui_theme import _logo_b64, apply_watermark, themed_plotly_chart


def render() -> None:
    if st.session_state.get("show_admin", False):
        render_admin()
        return

    apply_watermark(_logo_b64(), opacity=0.04)
    render_dashboard_shell("მენეჯერის ხედვა · ყველა მაღაზია")

    data = prepare_dashboard_data(None, sidebar_nav=True)
    if data is None:
        return
    inv, lines, d_start, d_end = data

    page = st.session_state.get("current_page", "დაფა")

    if page == "დაფა":
        render_dashboard(inv, lines, d_start, d_end, allowed_store_ids=None)
    elif page == "ანალიტიკა":
        st.subheader("📈 მაღაზიები — Return Rate")
        render_store_efficiency_section(inv, lines, d_start, d_end)
    elif page == "ანგარიშები":
        st.subheader("📂 ანგარიშები — შემოსავალი და წილი")
        daily_sr = daily_sales_returns_series(inv, lines, d_start, d_end)
        themed_plotly_chart(sales_returns_area(daily_sr), key="reports_sales_area")
        store_df = store_share_with_returns_pct(inv, lines, d_start, d_end)
        rsr = returns_vs_sales_by_store(inv, lines, d_start, d_end)
        c1, c2 = st.columns(2)
        with c1:
            themed_plotly_chart(store_donut(store_df), key="reports_donut")
        with c2:
            themed_plotly_chart(sales_returns_bar(rsr), key="reports_bars")
    elif page == "მარაგები":
        render_restock_recommendations_section(inv, d_start, d_end)
        st.markdown("---")
        st.subheader("📋 შეკვეთის დაგეგმვა")
        render_order_planning(allowed_store_ids=None)
    elif page == "პარტნიორები":
        st.subheader("🤝 პარტნიორები — გაყიდვები მაღაზიის მიხედვით")
        rsr = returns_vs_sales_by_store(inv, lines, d_start, d_end)
        if rsr.empty:
            st.info("ამ პერიოდში პარტნიორების მონაცემები არ არის.")
        else:
            themed_plotly_chart(sales_returns_bar(rsr.head(20)), key="partners_bars")
        st.text_input("🔍 მოძებნეთ პარტნიორი...", key="partner_search")
    else:
        st.session_state.current_page = "დაფა"
        st.rerun()

    render_floating_ai_chat()

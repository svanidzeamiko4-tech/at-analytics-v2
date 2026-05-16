"""Manager dashboard — full network access."""

from __future__ import annotations

import streamlit as st

from dashboard_core import render_dashboard_page
from pages.admin_panel import render as render_admin
from pages.order_planning import render as render_order_planning
from ui_theme import _logo_b64, apply_watermark


def render() -> None:
    if st.session_state.get("show_admin", False):
        render_admin()
        return

    apply_watermark(_logo_b64(), opacity=0.04)

    tab_dashboard, tab_overview = st.tabs(
        ["📊 დაშბორდი", "👁️ დისტრიბუტორების მიმოხილვა"]
    )

    with tab_dashboard:
        render_dashboard_page(
            allowed_store_ids=None,
            subtitle="მენეჯერის ხედვა · ყველა მაღაზია",
            show_ai_chat=True,
        )

    with tab_overview:
        render_order_planning(allowed_store_ids=None)

"""Distributor dashboard — assigned stores only."""

from __future__ import annotations

import streamlit as st

from auth.auth import get_allowed_store_ids, get_current_user
from dashboard_core import render_dashboard_page
from pages.order_planning import render as render_order_planning


def render() -> None:
    user = get_current_user() or {}
    store_ids = get_allowed_store_ids()
    allowed: list[int] | None
    if store_ids is None:
        allowed = None
    else:
        allowed = list(store_ids)
    n = 0 if store_ids is None else len(store_ids)
    subtitle = f"დისტრიბუტორი · {user.get('display_name', '')} · მაღაზიები: {n}"

    tab_dashboard, tab_orders = st.tabs(["📊 დაშბორდი", "📋 შეკვეთის დაგეგმვა"])

    with tab_dashboard:
        if store_ids is not None and not store_ids:
            st.warning(
                "თქვენს ანგარიშს არ აქვს მიბმული მაღაზიები. "
                "მენეჯერმა უნდა დაამატოს `user_stores` ცხრილში."
            )
        render_dashboard_page(
            allowed_store_ids=allowed,
            subtitle=subtitle,
            show_ai_chat=True,
        )

    with tab_orders:
        if store_ids is not None and not store_ids:
            st.warning("მაღაზიები არ არის მიბმული — შეკვეთის დაგეგმვა ვერ შესრულდება.")
            return
        render_order_planning(allowed_store_ids=allowed)

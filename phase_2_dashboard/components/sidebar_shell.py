"""Sidebar navigation shell — menu, filters, collapse."""

from __future__ import annotations

from datetime import date

import streamlit as st

from data_loader import preset_range


def render_sidebar_filters(today: date) -> None:
    """Date presets + custom range (collapsible on mobile via CSS)."""
    with st.sidebar.expander("ფილტრები", expanded=True):
        st.caption("პერიოდი")
        presets = ["7 დღე", "15 დღე", "1 თვე", "6 თვე", "1 წელი"]
        for i, label in enumerate(presets):
            if st.button(label, use_container_width=True, key=f"sb_pre_{i}"):
                st.session_state["preset"] = label
                st.session_state["d_start"], st.session_state["d_end"] = preset_range(
                    label, today
                )
                st.session_state["cust_start"] = st.session_state["d_start"]
                st.session_state["cust_end"] = st.session_state["d_end"]
                st.rerun()
        st.date_input("დაწყება", key="cust_start")
        st.date_input("დასასრული", key="cust_end")
        st.caption("რეგიონი · პარტნიორი · პროდუქტი — მალე")


def render_sidebar_nav(active: str = "dashboard") -> None:
    """Icon-style nav (routes map to existing app views)."""
    items = [
        ("dashboard", "დაფა"),
        ("analytics", "ანალიტიკა"),
        ("reports", "ანგარიშები"),
        ("inventory", "მარაგები"),
        ("partners", "პარტნიორები"),
    ]
    st.markdown('<div class="sb-nav">', unsafe_allow_html=True)
    for key, label in items:
        cls = "sb-nav-item sb-nav-item--active" if key == active else "sb-nav-item"
        st.markdown(
            f'<div class="{cls}" data-nav="{key}"><span class="sb-dot"></span>{label}</div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)
    st.session_state.setdefault("nav_view", active)

"""Dashboard top toolbar — mobile menu trigger + export stubs."""

from __future__ import annotations

import streamlit as st


def render_dashboard_toolbar() -> None:
    st.markdown(
        """
    <div class="at-topbar">
        <button type="button" class="at-hamburger" id="at-menu-btn" aria-label="მენიუ">☰</button>
        <span style="color:var(--color-text-secondary);font-size:0.9rem;">AT Analytics</span>
    </div>
    <div id="at-sidebar-overlay" class="at-sidebar-overlay" aria-hidden="true"></div>
    """,
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4, _ = st.columns([1, 1, 1, 1, 2])
    with c1:
        if st.button("🌙 Dark", key="tb_dark", help="მომავალი: ღია თემა"):
            st.toast("Dark mode უკვე ჩართულია.")
    with c2:
        if st.button("PDF", key="tb_pdf"):
            st.info("PDF ექსპორტი — მალე.")
    with c3:
        if st.button("CSV", key="tb_csv"):
            st.info("CSV ექსპორტი — მალე.")
    with c4:
        if st.button("Share", key="tb_share"):
            st.info("Snapshot ლინკი — მალე.")

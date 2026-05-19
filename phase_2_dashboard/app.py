"""
AT ANALYTICS — Phase 2 Streamlit dashboard (read-only ``amiko_v3.db``).

Run from project root:
  streamlit run phase_2_dashboard/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

LOGO_PATH = Path(__file__).resolve().parent / "assets" / "at_analytics_logo.png"
logo_image = str(LOGO_PATH) if LOGO_PATH.is_file() else "📊"

st.set_page_config(
    page_title="AT ANALYTICS - Supply Chain Report",
    page_icon=logo_image,
    layout="wide",
    initial_sidebar_state="expanded",
)


def _css() -> str:
    return """
[data-testid="stSidebarNav"] {
    display: none !important;
}
section[data-testid="stSidebarNav"] {
    display: none !important;
}
"""


st.markdown(f"<style>{_css()}</style>", unsafe_allow_html=True)

# Re-export theme tokens (constants live in ui_theme.py).
from ui_theme import (  # noqa: E402
    BG,
    BORDER,
    CARD,
    EMERALD,
    EMERALD_DIM,
    FONT_FAMILY,
    GEO,
    GRID,
    HEADER_NEON_CYAN,
    MUTED,
    NEON_BLUE,
    NEON_BLUE_DIM,
    PAGE_SUB,
    PLOTLY_STREAMLIT_CONFIG,
    RED_RET,
    TEXT,
)

from dashboard_core import render_dashboard_page  # noqa: E402,F401


def main() -> None:
    from auth.auth import get_current_user, get_role, is_authenticated, logout, restore_session
    from pages.distributor_view import render as render_distributor
    from pages.login import render as render_login
    from pages.manager_view import render as render_manager

    restore_session()
    if not is_authenticated():
        render_login()
        return

    user = get_current_user()
    role = get_role()
    with st.sidebar:
        st.markdown(f"**{user.get('display_name', '')}** · `{user.get('role', '')}`")
        if st.button("გასვლა", key="auth_logout", use_container_width=True):
            st.session_state.pop("show_admin", None)
            logout()
            st.rerun()
        if role == "manager":
            st.markdown("---")
            if st.button("⚙️ ადმინ პანელი", use_container_width=True, key="mgr_admin_toggle"):
                st.session_state["show_admin"] = not st.session_state.get("show_admin", False)

    if role == "manager":
        render_manager()
    elif role == "distributor":
        render_distributor()
    else:
        st.error("უცნობი მომხმარებლის როლი.")
        logout()
        st.rerun()


main()

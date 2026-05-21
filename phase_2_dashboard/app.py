"""
AT ANALYTICS — Phase 2 Streamlit dashboard (read-only ``amiko_v3.db``).

Run from project root:
  streamlit run phase_2_dashboard/app.py
"""

from __future__ import annotations

import html
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

from ui_theme import apply_theme_css, is_dark_mode  # noqa: E402

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True
apply_theme_css()


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


def main() -> None:
    from core.config import get_settings
    from core.production_check import run_production_checks

    if get_settings().is_production:
        run_production_checks(strict=True)

    from auth.auth import get_current_user, get_role, is_authenticated, logout, restore_session
    from pages.distributor_view import render as render_distributor
    from pages.login import render as render_login
    from pages.manager_view import render as render_manager
    from ui_shell import init_app_state

    init_app_state()
    restore_session()
    if not is_authenticated():
        render_login()
        return
    user = get_current_user()
    role = get_role()
    with st.sidebar:
        st.markdown(
            '<div style="font-weight:600;color:var(--color-primary, #00c2d1);'
            'letter-spacing:0.06em;margin-bottom:8px;">AT ANALYTICS</div>',
            unsafe_allow_html=True,
        )
        name = html.escape(str(user.get("display_name", "")))
        role_label = html.escape(str(user.get("role", "")))
        if is_dark_mode():
            text_color, badge_bg, badge_color = "#E5E7EB", "#1e293b", "#7dd3fc"
        else:
            text_color, badge_bg, badge_color = "#0f172a", "#eff6ff", "#2563eb"
        st.markdown(
            f'<p class="sidebar-user" style="color:{text_color};font-size:0.95rem;'
            f'margin:0 0 12px 0;line-height:1.5;">'
            f"<strong>{name}</strong> · "
            f'<span style="background:{badge_bg};color:{badge_color};'
            f'padding:3px 10px;border-radius:8px;font-size:0.82rem;'
            f'font-weight:600;">{role_label}</span></p>',
            unsafe_allow_html=True,
        )
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

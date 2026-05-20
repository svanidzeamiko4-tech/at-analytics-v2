"""AT Analytics — split-screen login."""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

from auth.auth import login
from auth.users import init_auth_db
from ui_shell import apply_theme_css, init_app_state
from ui_theme import (
    BG,
    BORDER,
    CARD,
    FONT_BODY,
    FONT_HEADING,
    GEO,
    GOOGLE_FONTS_URL,
    MUTED,
    PRIMARY,
    PRIMARY_DARK,
    PRIMARY_GLOW,
    TEXT,
)

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "at_analytics_logo.png"


def _logo_b64() -> str:
    if LOGO_PATH.is_file():
        with open(str(LOGO_PATH), "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""


def _login_css() -> str:
    return f"""
    @import url('{GOOGLE_FONTS_URL}');
    [data-testid="stSidebar"] {{ display: none !important; }}
    [data-theme="dark"] .stApp {{
        background: {BG} !important;
        font-family: {FONT_BODY};
    }}
    [data-theme="light"] .stApp {{
        background: linear-gradient(to bottom, #F8FAFC 0%, #F1F5F9 100%) !important;
        font-family: {FONT_BODY};
    }}
    [data-theme="dark"] .login-hero-wrap {{
        padding: 48px 32px;
        min-height: 70vh;
        display: flex;
        flex-direction: column;
        justify-content: center;
        background: radial-gradient(ellipse at 30% 20%, {PRIMARY_GLOW}, transparent 55%), {BG};
        border-radius: 16px;
    }}
    [data-theme="light"] .login-hero-wrap {{
        padding: 48px 32px;
        min-height: 70vh;
        display: flex;
        flex-direction: column;
        justify-content: center;
        background: radial-gradient(ellipse at 30% 20%, rgba(0,194,209,0.08), transparent 55%), #F8FAFC;
        border-radius: 16px;
    }}
    .login-glass-wrap {{
        padding: 32px 16px;
        display: flex;
        align-items: center;
        justify-content: center;
    }}
    [data-theme="dark"] .login-glass {{
        width: 100%;
        max-width: 400px;
        padding: 24px;
        border-radius: 16px;
        border: 1px solid rgba(255,255,255,0.05);
        background: rgba(17, 24, 39, 0.85);
        backdrop-filter: blur(12px);
        box-shadow: 0 24px 48px rgba(0, 0, 0, 0.4);
    }}
    [data-theme="light"] .login-glass {{
        width: 100%;
        max-width: 400px;
        padding: 24px;
        border-radius: 16px;
        border: 1px solid #e2e8f0;
        background: rgba(255, 255, 255, 0.92);
        backdrop-filter: blur(12px);
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
    }}
    [data-theme="dark"] .stTextInput > div > div > input {{
        background: {CARD} !important;
        border: 1px solid {BORDER} !important;
        color: {TEXT} !important;
        min-height: 44px !important;
        border-radius: 12px !important;
    }}
    [data-theme="light"] .stTextInput > div > div > input {{
        background: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        color: #0f172a !important;
        min-height: 44px !important;
        border-radius: 12px !important;
    }}
    [data-theme="dark"] .stTextInput label {{ color: {MUTED} !important; }}
    [data-theme="light"] .stTextInput label {{ color: #475569 !important; }}
    div[data-testid="stForm"] button {{
        min-height: 44px !important;
        background: {PRIMARY} !important;
        color: {BG} !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
    }}
    div[data-testid="stForm"] button:hover {{ background: {PRIMARY_DARK} !important; }}
    @media (max-width: 768px) {{
        .login-hero-wrap {{ min-height: auto; padding: 32px 16px; }}
    }}
    """


def render() -> None:
    init_auth_db()
    init_app_state()
    apply_theme_css()
    st.markdown(f"<style>{_login_css()}</style>", unsafe_allow_html=True)

    b64 = _logo_b64()
    logo_html = (
        f'<img src="data:image/png;base64,{b64}" alt="AT Analytics" '
        f'style="width:120px;filter:drop-shadow(0 0 24px {PRIMARY_GLOW});" />'
        if b64
        else "📊"
    )
    sub = GEO["report_sub"]

    col_hero, col_form = st.columns([1.1, 0.9])
    with col_hero:
        st.markdown(
            f"""
        <div class="login-hero-wrap">
            <div style="margin-bottom:24px;">{logo_html}</div>
            <h1 style="font-family:{FONT_HEADING};font-size:2rem;font-weight:700;
                color:{PRIMARY};letter-spacing:-0.5px;margin:0 0 12px 0;">AT Analytics</h1>
            <p style="color:{MUTED};font-size:1rem;max-width:360px;line-height:1.5;">{sub}</p>
        </div>
        """,
            unsafe_allow_html=True,
        )
    with col_form:
        st.markdown('<div class="login-glass-wrap"><div class="login-glass">', unsafe_allow_html=True)
        st.markdown(
            f'<h2 style="font-family:{FONT_HEADING};font-size:1.25rem;color:{TEXT};'
            f'margin:0 0 16px 0;font-weight:600;">შესვლა</h2>',
            unsafe_allow_html=True,
        )
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input(
                "მომხმარებელი", placeholder="შეიყვანეთ მომხმარებელი"
            )
            password = st.text_input("პაროლი", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("შესვლა →", use_container_width=True)
        st.markdown("</div></div>", unsafe_allow_html=True)

    if submitted:
        if not username.strip() or not password:
            st.error("შეიყვანეთ მომხმარებელი და პაროლი.")
        elif login(username.strip(), password):
            st.rerun()
        else:
            st.error("მომხმარებელი ან პაროლი არასწორია")

    st.caption("AT Analytics © 2026")

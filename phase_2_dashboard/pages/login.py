"""AT Analytics — styled login page."""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

from auth.auth import login
from auth.users import init_auth_db
from ui_theme import (
    BG,
    BORDER,
    CARD,
    CARD_PADDING,
    FONT_BODY,
    FONT_HEADING,
    GOOGLE_FONTS_URL,
    MUTED,
    PRIMARY,
    PRIMARY_DARK,
    PRIMARY_GLOW,
    RADIUS,
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
    .stApp {{ background: {BG} !important; font-family: {FONT_BODY}; }}
    .login-container {{
        max-width: 420px;
        margin: 60px auto 0 auto;
        padding: {CARD_PADDING};
        background: {CARD};
        border: 1px solid {BORDER};
        border-radius: {RADIUS};
        box-shadow: 0 0 32px {PRIMARY_GLOW};
    }}
    .login-container:hover {{ border-color: {PRIMARY}; box-shadow: 0 0 40px {PRIMARY_GLOW}; }}
    .login-logo {{ text-align: center; margin-bottom: 8px; }}
    .login-logo img {{ width: 90px; filter: drop-shadow(0 0 16px {PRIMARY_GLOW}); }}
    .login-title {{
        text-align: center;
        font-size: 1.8rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        color: {PRIMARY};
        margin: 0 0 4px 0;
        font-family: {FONT_HEADING};
    }}
    .login-sub {{ text-align: center; color: {MUTED}; font-size: 0.8rem; margin-bottom: 28px; }}
    .stTextInput > div > div > input {{
        background: {CARD} !important;
        border: 1px solid {BORDER} !important;
        border-radius: 12px !important;
        color: {TEXT} !important;
        caret-color: {PRIMARY} !important;
        padding: 12px 16px !important;
        font-family: {FONT_BODY} !important;
    }}
    .stTextInput > div > div > input:focus {{
        border-color: {PRIMARY} !important;
        box-shadow: 0 0 0 2px {PRIMARY_GLOW} !important;
    }}
    .stTextInput label {{ color: {MUTED} !important; }}
    div[data-testid="stForm"] > div:last-child button {{
        width: 100%;
        background: {PRIMARY} !important;
        color: {BG} !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 14px !important;
        font-weight: 600 !important;
        font-family: {FONT_BODY} !important;
    }}
    div[data-testid="stForm"] > div:last-child button:hover {{
        background: {PRIMARY_DARK} !important;
        box-shadow: 0 4px 20px {PRIMARY_GLOW} !important;
    }}
    """


def render() -> None:
    init_auth_db()
    st.markdown(f"<style>{_login_css()}</style>", unsafe_allow_html=True)

    b64 = _logo_b64()
    logo_html = f'<img src="data:image/png;base64,{b64}" />' if b64 else "📊"
    st.markdown(
        f"""
    <div class="login-container">
        <div class="login-logo">{logo_html}</div>
        <div class="login-title">AT ANALYTICS</div>
        <div class="login-sub">ბიზნეს ანალიტიკისა და მარაგების მართვის სისტემა</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    _, col, _ = st.columns([1, 2, 1])
    with col:
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input(
                "მომხმარებელი", placeholder="შეიყვანეთ მომხმარებელი"
            )
            password = st.text_input(
                "პაროლი", type="password", placeholder="••••••••"
            )
            submitted = st.form_submit_button("შესვლა →", use_container_width=True)

        if submitted:
            if not username.strip() or not password:
                st.error("შეიყვანეთ მომხმარებელი და პაროლი.")
            elif login(username.strip(), password):
                st.rerun()
            else:
                st.error("❌ მომხმარებელი ან პაროლი არასწორია")

    st.markdown(
        """
    <div style="text-align:center;color:#374151;font-size:0.72rem;margin-top:16px;">
        AT Analytics © 2026 · Powered by Anthropic Claude
    </div>
    """,
        unsafe_allow_html=True,
    )

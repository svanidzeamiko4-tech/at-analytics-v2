"""AT Analytics — styled login page."""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

from auth.auth import login
from auth.users import init_auth_db

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "at_analytics_logo.png"


def _logo_b64() -> str:
    if LOGO_PATH.is_file():
        with open(str(LOGO_PATH), "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""


def render() -> None:
    init_auth_db()
    st.markdown(
        """
    <style>
    .stApp { background: linear-gradient(135deg, #0a0e1a 0%, #0e1117 50%, #0a1628 100%) !important; }

    .login-container {
        max-width: 420px;
        margin: 60px auto 0 auto;
        padding: 40px;
        background: rgba(26,28,36,0.95);
        border: 1px solid rgba(34,211,238,0.2);
        border-radius: 20px;
        box-shadow: 0 0 60px rgba(34,211,238,0.08), 0 20px 60px rgba(0,0,0,0.5);
    }
    .login-logo {
        text-align: center;
        margin-bottom: 8px;
    }
    .login-logo img {
        width: 90px;
        filter: drop-shadow(0 0 20px rgba(34,211,238,0.4));
    }
    .login-title {
        text-align: center;
        font-size: 1.8rem;
        font-weight: 700;
        letter-spacing: 0.1em;
        color: #22d3ee;
        margin: 0 0 4px 0;
        font-family: 'Segoe UI', system-ui, sans-serif;
    }
    .login-sub {
        text-align: center;
        color: #6b7280;
        font-size: 0.8rem;
        margin-bottom: 28px;
    }
    .stTextInput > div > div > input {
        background: #1a1c24 !important;
        border: 1px solid rgba(34,211,238,0.3) !important;
        border-radius: 10px !important;
        color: #f0f2f6 !important;
        caret-color: #22d3ee !important;
        padding: 12px 16px !important;
    }
    .stTextInput > div > div > input::placeholder {
        color: #4b5563 !important;
    }
    .stTextInput > div > div > input:focus {
        border-color: rgba(34,211,238,0.6) !important;
        box-shadow: 0 0 0 2px rgba(34,211,238,0.15) !important;
    }
    .stTextInput label { color: #9aa0ab !important; font-size: 0.85rem !important; }
    .stTextInput > div > div > button {
        background: #22d3ee !important;
        border: none !important;
        border-radius: 0 10px 10px 0 !important;
    }

    div[data-testid="stForm"] > div:last-child button {
        width: 100%;
        background: linear-gradient(135deg, #0891b2, #0e7490) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 14px !important;
        font-size: 1rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.05em !important;
        cursor: pointer !important;
        transition: all 0.2s !important;
    }
    div[data-testid="stForm"] > div:last-child button:hover {
        background: linear-gradient(135deg, #06b6d4, #0891b2) !important;
        box-shadow: 0 4px 20px rgba(34,211,238,0.3) !important;
    }
    .login-footer {
        text-align: center;
        color: #374151;
        font-size: 0.72rem;
        margin-top: 24px;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

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

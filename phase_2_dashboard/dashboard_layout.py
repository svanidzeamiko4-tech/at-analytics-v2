"""Layout helpers (CSS, header, dates) — uses ui_theme only."""

from __future__ import annotations

import base64
import html
from datetime import date
from pathlib import Path

import streamlit as st

from data_loader import preset_range
from ui_theme import (
    BG,
    BORDER,
    CARD,
    EMERALD,
    FONT_FAMILY,
    GEO,
    HEADER_NEON_CYAN,
    MUTED,
    NEON_BLUE,
    PAGE_SUB,
    TEXT,
)

LOGO_PATH = Path(__file__).resolve().parent / "assets" / "at_analytics_logo.png"


def apply_css() -> None:
    st.markdown(
        f"""
        <style>
        .stApp {{ background-color: {BG}; color: {TEXT}; }}
        [data-testid="stSidebar"] {{
            background-color: {CARD};
            border-right: 1px solid {BORDER};
        }}
        [data-testid="stSidebar"] .stMarkdown h3 {{ color: {TEXT}; font-weight: 600; }}
        .dash-card {{
            background-color: {CARD};
            border: 1px solid {BORDER};
            border-radius: 14px;
            padding: 18px 20px 16px 20px;
            margin-bottom: 14px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.35);
        }}
        .dash-card h3 {{ margin: 0 0 4px 0; font-size: 0.78rem; color: {MUTED}; text-transform: uppercase; letter-spacing: 0.08em; }}
        .dash-hero-num {{ font-size: 1.85rem; font-weight: 700; letter-spacing: -0.02em; }}
        .dash-hero-sub {{ color: {MUTED}; font-size: 0.88rem; margin-top: 4px; }}
        .magic-card {{
            background: linear-gradient(145deg, {CARD} 0%, #14161f 100%);
            border: 1px solid rgba(34, 211, 238, 0.35);
            border-radius: 14px;
            padding: 16px 18px;
            margin-bottom: 12px;
            box-shadow: 0 0 0 1px rgba(34,211,238,0.06), 0 8px 32px rgba(0,0,0,0.45);
        }}
        .magic-card .title {{ color: {NEON_BLUE}; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 600; }}
        .magic-card .store {{ font-size: 1.05rem; font-weight: 600; margin: 8px 0 6px 0; color: {TEXT}; }}
        .magic-card .amt {{ font-size: 1.35rem; font-weight: 700; color: {EMERALD}; }}
        .magic-card .conf {{ color: {MUTED}; font-size: 0.82rem; margin-top: 8px; }}
        h1 {{ color: {TEXT} !important; font-weight: 700 !important; letter-spacing: -0.03em; }}
        .page-sub {{
            color: {PAGE_SUB};
            font-size: 0.8rem;
            font-weight: 400;
            margin-top: -4px;
            line-height: 1.4;
            letter-spacing: 0.01em;
        }}
        section[data-testid="stMain"] [data-testid="stHorizontalBlock"]:first-of-type > [data-testid="column"]:first-child,
        section[data-testid="stMain"] [data-testid="stHorizontalBlock"]:first-of-type > [data-testid="column"]:first-child > div {{
            background: transparent !important;
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
            outline: none !important;
        }}
        section[data-testid="stMain"] [data-testid="stHorizontalBlock"]:first-of-type > [data-testid="column"]:first-child [data-testid="element-container"] {{
            background: transparent !important;
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
        }}
        section[data-testid="stMain"] [data-testid="stHorizontalBlock"]:first-of-type > [data-testid="column"]:first-child [data-testid="stImage"],
        section[data-testid="stMain"] [data-testid="stHorizontalBlock"]:first-of-type > [data-testid="column"]:first-child [data-testid="stImage"] > div,
        section[data-testid="stMain"] [data-testid="stHorizontalBlock"]:first-of-type > [data-testid="column"]:first-child [data-testid="stImage"] figure,
        section[data-testid="stMain"] [data-testid="stHorizontalBlock"]:first-of-type > [data-testid="column"]:first-child [data-testid="stImage"] img {{
            background: transparent !important;
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
            outline: none !important;
        }}
        section[data-testid="stMain"] [data-testid="stHorizontalBlock"]:first-of-type > [data-testid="column"]:first-child [data-testid="stImage"] > div {{
            padding: 0 !important;
            margin: 0 !important;
        }}
        .brand-titles {{
            min-width: 0;
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: center;
            padding: 0.1rem 0 0.35rem 0;
        }}
        .brand-title {{
            font-family: {FONT_FAMILY};
            font-size: clamp(1.5rem, 2.6vw, 1.95rem);
            font-weight: 700;
            letter-spacing: 0.07em;
            color: {HEADER_NEON_CYAN};
            line-height: 1.12;
            margin: 0;
        }}
        .brand-sub {{
            font-family: {FONT_FAMILY};
            font-size: 0.8rem;
            font-weight: 400;
            color: {PAGE_SUB};
            margin: 0.38rem 0 0 0;
            line-height: 1.45;
            letter-spacing: 0.01em;
            max-width: 56rem;
        }}
        .ai-main-stack {{ margin: 0.85rem 0 1.35rem 0; }}
        .ai-main-cap {{
            font-family: {FONT_FAMILY};
            color: {MUTED};
            font-size: 0.72rem;
            font-weight: 500;
            letter-spacing: 0.04em;
            margin: 0 0 0.42rem 0;
        }}
        .ai-main-banner {{
            font-family: {FONT_FAMILY};
            background: linear-gradient(135deg, #152642 0%, #1a2d4a 55%, #162238 100%);
            border: 1px solid rgba(0, 255, 255, 0.22);
            border-radius: 12px;
            padding: 14px 18px;
            color: {HEADER_NEON_CYAN};
            font-size: 0.94rem;
            line-height: 1.48;
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.35);
        }}
        [data-testid="stMetric"] {{
            background-color: {CARD};
            border: 1px solid {BORDER};
            border-radius: 12px;
            padding: 14px 16px;
            min-height: 104px;
        }}
        [data-testid="stMetric"] label {{ color: {MUTED} !important; }}
        [data-testid="stMetric"] [data-testid="stMetricValue"] {{ color: {TEXT} !important; }}
        div[data-testid="stMetricDelta"] {{ font-size: 0.82rem; }}
        div[data-testid="stVerticalBlockBorderWrapper"] > div {{
            border-color: {BORDER} !important;
        }}
        .st-key-fab_chat_toggle {{
            position: fixed !important;
            bottom: 30px;
            right: 30px;
            z-index: 9999;
            width: 60px;
            height: 60px;
            margin: 0 !important;
            padding: 0 !important;
        }}
        .st-key-fab_chat_toggle button,
        .floating-chat-btn {{
            width: 60px !important;
            height: 60px !important;
            min-height: 60px !important;
            border-radius: 50% !important;
            background: linear-gradient(135deg, #22d3ee, #11CAA0) !important;
            border: none !important;
            cursor: pointer;
            font-size: 28px !important;
            line-height: 1 !important;
            padding: 0 !important;
            color: #0e1117 !important;
            box-shadow: 0 4px 20px rgba(34, 211, 238, 0.4);
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }}
        .st-key-fab_chat_toggle button:hover,
        .floating-chat-btn:hover {{
            transform: scale(1.1);
            box-shadow: 0 6px 28px rgba(34, 211, 238, 0.6);
        }}
        .st-key-fab_chat_toggle button:focus-visible {{
            outline: 2px solid {NEON_BLUE};
            outline-offset: 3px;
        }}
        .st-key-ai_chat_panel {{
            position: fixed !important;
            bottom: 100px;
            right: 30px;
            z-index: 9998;
            width: min(440px, calc(100vw - 48px));
            max-height: min(72vh, 640px);
            overflow-y: auto;
            margin: 0 !important;
            padding: 0 !important;
            animation: aiChatPanelIn 0.22s ease-out;
        }}
        .st-key-ai_chat_panel > div {{
            background: linear-gradient(145deg, {CARD} 0%, #14161f 100%);
            border: 1px solid rgba(34, 211, 238, 0.35);
            border-radius: 16px;
            padding: 12px 16px 16px;
            box-shadow: 0 12px 48px rgba(0, 0, 0, 0.55);
        }}
        .st-key-fab_chat_close button {{
            width: 2rem !important;
            min-height: 2rem !important;
            padding: 0 !important;
            border-radius: 8px !important;
            border: 1px solid {BORDER} !important;
            background: {CARD} !important;
            color: {TEXT} !important;
        }}
        @keyframes aiChatPanelIn {{
            from {{ opacity: 0; transform: translateY(12px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        @media (max-width: 768px) {{
            [data-testid="stPlotlyChart"] {{ min-height: 0 !important; }}
            .st-key-donut, .st-key-bars_sr, .st-key-products_all, .st-key-hero_area_sr {{
                width: 100% !important;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def floating_chat_js() -> None:
    st.markdown(
        """
        <script>
        (function () {
            const doc = window.parent.document;
            const fab = doc.querySelector(".st-key-fab_chat_toggle button");
            if (fab) {
                fab.classList.add("floating-chat-btn");
                fab.setAttribute("aria-label", "AI დისტრიბუციის ასისტენტი");
            }
            const panel = doc.querySelector(".st-key-ai_chat_panel");
            if (panel) {
                panel.setAttribute("role", "dialog");
                panel.setAttribute("aria-label", "AI ჩათი");
            }
        })();
        </script>
        """,
        unsafe_allow_html=True,
    )


def init_sidebar_dates(today: date) -> None:
    if "preset" not in st.session_state:
        st.session_state["preset"] = "1 თვე"
    if "d_start" not in st.session_state or "d_end" not in st.session_state:
        st.session_state["d_start"], st.session_state["d_end"] = preset_range(
            st.session_state["preset"], today
        )
    if "cust_start" not in st.session_state:
        st.session_state["cust_start"] = st.session_state["d_start"]
        st.session_state["cust_end"] = st.session_state["d_end"]


def render_brand_header() -> None:
    sub = html.escape(GEO["report_sub"])
    c_logo, c_txt = st.columns([0.11, 0.89], gap="small")
    with c_logo:
        if LOGO_PATH.is_file():
            with open(LOGO_PATH, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            st.markdown(
                f'<img src="data:image/png;base64,{b64}" '
                f'style="width:100%;max-width:90px;background:transparent;'
                f'mix-blend-mode:screen;" alt="AT Analytics" />',
                unsafe_allow_html=True,
            )
    with c_txt:
        st.markdown(
            f'<div class="brand-titles"><div class="brand-title">AT ANALYTICS</div>'
            f'<p class="brand-sub">{sub}</p></div>',
            unsafe_allow_html=True,
        )

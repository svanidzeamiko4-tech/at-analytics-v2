"""
App shell — header, theme toggle, sidebar navigation.
"""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

from ui_theme import GEO, GOOGLE_FONTS_URL, PRIMARY, load_design_css

LOGO_PATH = Path(__file__).resolve().parent / "assets" / "at_analytics_logo.png"
PAGES = ["დაფა", "ანალიტიკა", "ანგარიშები", "მარაგები", "პარტნიორები"]


def get_theme_name() -> str:
    """Source of truth: ``st.session_state.dark_mode``."""
    return "dark" if st.session_state.get("dark_mode", True) else "light"


def init_app_state() -> None:
    st.session_state.setdefault("current_page", "დაფა")
    if "dark_mode" not in st.session_state:
        st.session_state.dark_mode = True
    st.session_state["theme"] = get_theme_name()


def inject_theme_bridge() -> None:
    """
    Force browser ``data-theme`` to match Python session (overrides localStorage drift).
    """
    is_dark = bool(st.session_state.get("dark_mode", True))
    theme_value = "dark" if is_dark else "light"
    st.markdown(
        f"""
        <script>
        (function () {{
            var targetTheme = "{theme_value}";
            function applyTheme(el) {{
                if (el) el.setAttribute("data-theme", targetTheme);
            }}
            applyTheme(document.documentElement);
            applyTheme(document.body);
            try {{
                var app = document.querySelector(".stApp");
                if (app) applyTheme(app);
                var view = document.querySelector('[data-testid="stAppViewContainer"]');
                if (view) applyTheme(view);
            }} catch (e) {{}}
            try {{
                if (window.parent && window.parent.document) {{
                    applyTheme(window.parent.document.documentElement);
                    applyTheme(window.parent.document.body);
                }}
            }} catch (e) {{}}
            try {{
                localStorage.setItem("theme", targetTheme);
            }} catch (e) {{}}
            window.toggleTheme = function () {{
                var html = document.documentElement;
                var next = html.getAttribute("data-theme") === "dark" ? "light" : "dark";
                html.setAttribute("data-theme", next);
                try {{ localStorage.setItem("theme", next); }} catch (e) {{}}
            }};
        }})();
        </script>
        """,
        unsafe_allow_html=True,
    )


def apply_theme_css() -> None:
    """Load scoped CSS + inject theme (Python state is authoritative)."""
    is_dark = bool(st.session_state.get("dark_mode", True))
    theme_value = "dark" if is_dark else "light"
    inject_theme_bridge()
    st.markdown(
        f"""
        <style>
        {load_design_css()}
        @import url('{GOOGLE_FONTS_URL}');
        html, :root {{
            color-scheme: {"dark" if is_dark else "light"};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _logo_html() -> str:
    if LOGO_PATH.is_file():
        b64 = base64.b64encode(LOGO_PATH.read_bytes()).decode()
        glow = (
            "drop-shadow(0 0 12px rgba(0,194,209,0.35))"
            if st.session_state.get("dark_mode", True)
            else "none"
        )
        return (
            f'<img src="data:image/png;base64,{b64}" alt="AT Analytics" '
            f'style="width:72px;max-width:100%;filter:{glow};" />'
        )
    return '<span style="font-size:2.5rem;">📊</span>'


def render_app_header(role_hint: str | None = None) -> None:
    """Logo, title, theme / export buttons."""
    st.markdown('<div class="at-header-bar">', unsafe_allow_html=True)
    col_logo, col_title, col_actions = st.columns([1, 4, 3])
    logo = _logo_html()
    sub = GEO["report_sub"]

    with col_logo:
        st.markdown(
            f'<div style="text-align:center;padding:8px 0;">{logo}'
            f'<div style="font-weight:700;color:{PRIMARY};font-size:0.72rem;'
            f'letter-spacing:0.08em;margin-top:6px;">AT ANALYTICS</div></div>',
            unsafe_allow_html=True,
        )
    with col_title:
        st.markdown('<div class="main-title">AT ANALYTICS</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="subtitle">{sub}</div>', unsafe_allow_html=True)
    with col_actions:
        b1, b2, b3, b4 = st.columns(4)
        with b1:
            theme_label = "☀️ Light" if st.session_state.dark_mode else "🌙 Dark"
            if st.button(theme_label, key="btn_theme", use_container_width=True):
                st.session_state.dark_mode = not st.session_state.dark_mode
                st.session_state["theme"] = (
                    "dark" if st.session_state.dark_mode else "light"
                )
                st.rerun()
        with b2:
            if st.button("📄 PDF", use_container_width=True, key="shell_pdf"):
                st.toast("მზადდება PDF რეპორტი...", icon="📥")
        with b3:
            if st.button("📊 CSV", use_container_width=True, key="shell_csv"):
                st.toast("CSV ექსპორტი — მალე", icon="✅")
        with b4:
            if st.button("🔗 Share", use_container_width=True, key="shell_share"):
                st.toast("ბმული გაზიარებისთვის — მალე", icon="🔗")

    if role_hint:
        st.caption(f"📍 {role_hint} | გვერდი: **{st.session_state.current_page}**")
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("---")


def render_sidebar_navigation() -> None:
    """Interactive sidebar menu."""
    st.sidebar.markdown("### 🗺️ ნავიგაცია")
    for page in PAGES:
        current = st.session_state.current_page == page
        prefix = "🔹 " if current else "▫️ "
        btn_type = "primary" if current else "secondary"
        if st.sidebar.button(
            f"{prefix}{page}",
            type=btn_type,
            use_container_width=True,
            key=f"nav_{page}",
        ):
            st.session_state.current_page = page
            st.rerun()
    st.sidebar.markdown("---")
    st.sidebar.markdown("⚙️ **სისტემის სტატუსი**")
    st.sidebar.success("მონაცემები ჩატვირთულია")


def render_ai_box() -> None:
    st.markdown(
        '<div class="ai-box"><p class="ai-text">🧠 AI რეკომენდაცია: AI მოდელი ამუშავებს '
        "მონაცემებს მარაგების ოპტიმიზაციისთვის და პროგნოზირებისთვის...</p></div>",
        unsafe_allow_html=True,
    )

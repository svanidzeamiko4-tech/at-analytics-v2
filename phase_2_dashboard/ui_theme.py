"""Shared UI tokens — Modern SaaS Distribution Analytics design system."""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

_LOGO_PATH = Path(__file__).resolve().parent / "assets" / "at_analytics_logo.png"

_PKG = Path(__file__).resolve().parent

# --- Design system palette (2026 SaaS) ---
PRIMARY = "#00C2D1"
PRIMARY_DARK = "#00A8B5"
ACCENT = "#7C3AED"
BG = "#0B1120"
CARD = "#111827"
CARD_HOVER = "#1F2937"
BORDER = "#1F2937"
TEXT = "#E5E7EB"
MUTED = "#9CA3AF"
SUCCESS = "#22C55E"
WARNING = "#F59E0B"
DANGER = "#EF4444"
TOOLTIP_BG = "#0F172A"

PRIMARY_GLOW = "rgba(0, 194, 209, 0.35)"
PRIMARY_DIM = "rgba(0, 194, 209, 0.14)"
PLOTLY_GRID = "rgba(31, 41, 55, 0.08)"
ACCENT_DIM = "rgba(124, 58, 237, 0.14)"
SUCCESS_DIM = "rgba(16, 185, 129, 0.14)"

RADIUS = "16px"
CARD_PADDING = "24px"

FONT_HEADING = "'Inter', system-ui, sans-serif"
FONT_BODY = "'Inter', system-ui, sans-serif"
FONT_NUMBERS = "'Space Grotesk', 'Inter', system-ui, sans-serif"
FONT_FAMILY = FONT_BODY

# Legacy aliases (charts / older imports)
NEON_BLUE = PRIMARY
NEON_BLUE_DIM = PRIMARY_DIM
HEADER_NEON_CYAN = PRIMARY
EMERALD = SUCCESS
EMERALD_DIM = SUCCESS_DIM
RED_RET = DANGER
PAGE_SUB = MUTED
GRID = BORDER

GOOGLE_FONTS_URL = (
    "https://fonts.googleapis.com/css2?"
    "family=Inter:wght@400;500;600;700&"
    "family=Space+Grotesk:wght@500;600;700&display=swap"
)


def load_design_css() -> str:
    """Load static design-system files (tokens → base → components)."""
    chunks: list[str] = []
    for name in ("design-tokens.css", "base.css", "components.css"):
        path = _PKG / name
        if path.is_file():
            chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def _theme_palette() -> dict[str, str]:
    """Runtime palette from ``st.session_state.dark_mode`` (authoritative)."""
    is_dark = bool(st.session_state.get("dark_mode", True))
    if is_dark:
        return {
            "name": "dark",
            "bg": "#0B1120",
            "card": "#0F172A",
            "text": "#F1F5F9",
            "muted": "#94A3B8",
            "border": "#1F2937",
            "sidebar": "#111827",
            "input_bg": "#0F172A",
        }
    return {
        "name": "light",
        "bg": "#F4F7FB",
        "card": "#FFFFFF",
        "text": "#1E293B",
        "muted": "#64748B",
        "border": "#E5E7EB",
        "sidebar": "#FFFFFF",
        "input_bg": "#FFFFFF",
    }


def _runtime_theme_css(palette: dict[str, str]) -> str:
    """Overrides static token files — must run every rerun after toggle."""
    t = palette["name"]
    bg, card, text = palette["bg"], palette["card"], palette["text"]
    muted, border = palette["muted"], palette["border"]
    sidebar, input_bg = palette["sidebar"], palette["input_bg"]
    return f"""
html[data-theme="{t}"],
html[data-theme="{t}"] body,
html[data-theme="{t}"] .stApp,
html[data-theme="{t}"] [data-testid="stAppViewContainer"],
html[data-theme="{t}"] [data-testid="stMain"],
html[data-theme="{t}"] section.main {{
  background-color: {bg} !important;
  color: {text} !important;
}}
html[data-theme="{t}"] {{
  color-scheme: {"dark" if t == "dark" else "light"};
  --color-bg-main: {bg};
  --color-bg-secondary: {card};
  --color-bg-card: {card};
  --color-bg-soft: {card};
  --color-text-primary: {text};
  --color-text-secondary: {muted};
  --color-border: {border};
  --color-gradient-main: {bg};
}}
html[data-theme="{t}"] .card,
html[data-theme="{t}"] .at-card,
html[data-theme="{t}"] .stat-card,
html[data-theme="{t}"] .hero-card,
html[data-theme="{t}"] .card-glass,
html[data-theme="{t}"] .ai-box,
html[data-theme="{t}"] div[data-testid="stMetric"],
html[data-theme="{t}"] [data-testid="stMetric"] {{
  background-color: {card} !important;
  color: {text} !important;
  border-color: {border} !important;
}}
html[data-theme="{t}"] [data-testid="stSidebar"],
html[data-theme="{t}"] [data-testid="stSidebar"] > div {{
  background-color: {sidebar} !important;
  color: {text} !important;
}}
html[data-theme="{t}"] [data-testid="stSidebar"] * {{
  color: {text};
}}
html[data-theme="{t}"] .stMarkdown,
html[data-theme="{t}"] .stMarkdown p,
html[data-theme="{t}"] .stMarkdown li,
html[data-theme="{t}"] .stMarkdown span,
html[data-theme="{t}"] .stMarkdown h1,
html[data-theme="{t}"] .stMarkdown h2,
html[data-theme="{t}"] .stMarkdown h3,
html[data-theme="{t}"] label,
html[data-theme="{t}"] .main-title,
html[data-theme="{t}"] .subtitle {{
  color: {text} !important;
}}
html[data-theme="{t}"] .subtitle,
html[data-theme="{t}"] .stat-label {{
  color: {muted} !important;
}}
html[data-theme="{t}"] [data-testid="stTextInput"] input,
html[data-theme="{t}"] [data-testid="stNumberInput"] input,
html[data-theme="{t}"] [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
html[data-theme="{t}"] [data-testid="stDateInput"] input {{
  background-color: {input_bg} !important;
  color: {text} !important;
  border-color: {border} !important;
}}
html[data-theme="{t}"] [data-testid="stHeader"] {{
  background-color: {bg} !important;
}}
"""


def inject_theme_bridge() -> None:
    """Sync ``data-theme`` on DOM to match Python ``dark_mode``."""
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
        }})();
        </script>
        """,
        unsafe_allow_html=True,
    )


def apply_theme_css() -> None:
    """
    Inject theme on every rerun from ``st.session_state.dark_mode``.
    Static CSS files load first; runtime block overrides backgrounds/text.
    """
    if "dark_mode" not in st.session_state:
        st.session_state.dark_mode = True
    st.session_state["theme"] = get_theme_name()
    palette = _theme_palette()
    inject_theme_bridge()
    st.markdown(
        f"""
        <style>
        @import url('{GOOGLE_FONTS_URL}');
        {load_design_css()}
        {_runtime_theme_css(palette)}
        </style>
        """,
        unsafe_allow_html=True,
    )


def is_light_mode() -> bool:
    """True when light theme is active (``dark_mode`` is False)."""
    return not st.session_state.get("dark_mode", True)


def plotly_axis_style() -> dict[str, object]:
    """Axis dict for chart builders (final colors come from ``apply_plotly_theme``)."""
    is_dark = st.session_state.get("dark_mode", True)
    grid_color = "#1F2937" if is_dark else "#E5E7EB"
    text_color = "#E5E7EB" if is_dark else "#64748B"
    return dict(
        gridcolor=grid_color,
        zerolinecolor=grid_color,
        tickfont=dict(size=12, color=text_color),
    )


def get_theme_name() -> str:
    return "dark" if st.session_state.get("dark_mode", True) else "light"


def apply_plotly_theme(fig: object) -> object:
    """
    Repaint Plotly layout on every rerun (bypasses any frozen figure styling).
    Must run immediately before ``st.plotly_chart``.
    """
    is_dark = st.session_state.get("dark_mode", True)

    paper_bg = "#0B1120" if is_dark else "#F4F7FB"
    plot_bg = "#0F172A" if is_dark else "#FFFFFF"
    text_color = "#E5E7EB" if is_dark else "#111827"
    grid_color = "#1F2937" if is_dark else "#E5E7EB"
    hover_bg = "#151F32" if is_dark else "#FFFFFF"

    axis_style = dict(
        gridcolor=grid_color,
        zerolinecolor=grid_color,
        color=text_color,
        tickfont=dict(color=text_color, family="Inter, Fira GO, sans-serif"),
        title=dict(font=dict(color=text_color, family="Inter, Fira GO, sans-serif")),
    )

    fig.update_layout(
        paper_bgcolor=paper_bg,
        plot_bgcolor=plot_bg,
        font=dict(color=text_color, family="Inter, Fira GO, sans-serif", size=11),
        legend=dict(font=dict(color=text_color), bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(
            bgcolor=hover_bg,
            bordercolor=grid_color,
            font=dict(color=text_color, size=12),
        ),
    )
    fig.update_xaxes(**axis_style)
    fig.update_yaxes(**axis_style)

    fig.update_layout(title_font=dict(color=text_color))

    if fig.layout.annotations:
        fig.update_annotations(font=dict(color=text_color))

    pie_line = "#FFFFFF" if is_light_mode() else "#0F172A"
    fig.update_traces(textfont=dict(color=text_color))
    fig.update_traces(
        marker=dict(line=dict(color=pie_line)),
        selector=dict(type="pie"),
    )
    # Do not override scatter/line stroke colors (keep brand cyan/green data series).

    return fig


def themed_plotly_chart(
    fig: object,
    *,
    use_container_width: bool = True,
    config: dict | None = None,
    key: str | None = None,
    **kwargs: object,
) -> None:
    """Render Plotly with theme applied at display time (not at figure build time)."""
    theme = get_theme_name()
    render_key = f"{key}_{theme}" if key else None
    st.plotly_chart(
        apply_plotly_theme(fig),
        use_container_width=use_container_width,
        config=config if config is not None else PLOTLY_STREAMLIT_CONFIG,
        key=render_key,
        **kwargs,
    )


def chart_muted_color() -> str:
    return "#64748B" if is_light_mode() else MUTED


def chart_text_color() -> str:
    return "#0F172A" if is_light_mode() else TEXT


def chart_pie_line_color() -> str:
    return "#FFFFFF" if is_light_mode() else BG

GEO = {
    "report_sub": "ბიზნეს ანალიტიკისა და მარაგების მართვის სისტემა",
    "time_range": "თარიღის დიაპაზონი",
    "custom_dates": "მორგებული თარიღი",
    "start": "დაწყება",
    "end": "დასასრული",
    "active_range": "აქტიური",
    "total_label": "სულ",
    "invoices": "ინვოისები",
    "line_items": "ხაზები",
    "db_file": "ბაზა",
    "hero_title": "გაყიდვებისა და დაბრუნებების მიმოხილვა",
    "total_sales": "მთლიანი გაყიდვები",
    "total_returns": "მთლიანი დაბრუნებები",
    "returns_share_note": "გაყიდვების პროცენტი",
    "spark_caption": "შემოსავლის დინამიკა (დღიური, ინვოისი)",
    "net_revenue": "წმინდა შემოსავალი",
    "active_stores": "აქტიური მაღაზიები",
    "calendar_days": "დღეები (ფილტრი)",
    "donut_title": "შემოსავლის წილი მაღაზიაში (%)",
    "bars_title": "გაყიდვები vs დაბრუნებები მაღაზიის მიხედვით",
    "products_title": "ტოპ პროდუქტები რაოდენობით",
    "restock_heading": "მარაგების შევსების რჩევა",
    "restock_sub": (
        "ევრისტიკა: არჩეული პერიოდის საშუალო დღიური ინვოისის შემოსავალი × 1.75 "
        "(დაახლოებით 1–2 დღე). სიზუსტე 70–80% დეტერმინისტულია მაღაზია+პერიოდის ჰეშით."
    ),
    "restock_card_title": "რეკომენდებული შევსება · მომდევნო 1–2 დღე",
    "restock_avg": "საშუალო დღიური შემოსავალი",
    "restock_conf": "სიზუსტე",
    "no_data": "მონაცემები არ არის ამ დიაპაზონში",
    "no_db": "ბაზის ფაილი ვერ მოიძებნა",
    "db_open_err": "ბაზის გახსნა ვერ მოხერხდა",
    "invalid_range": "არასწორი დიაპაზონი",
    "gel": "ლარი",
    "qty_axis": "რაოდენობა",
    "gel_axis": "ლარი (GEL)",
    "bar_sales": "გაყიდვები (ხაზი ≥ 0)",
    "bar_returns": "დაბრუნებები (კრედიტი)",
    "hero_bar_total_sales": "ჯამური გაყიდვები",
    "hero_bar_total_returns": "ჯამური დაბრუნებები",
    "hero_area_caption": "გაყიდვები და დაბრუნებები (დღიური, ხაზი)",
    "delta_returns_vs_sales": "დაბრუნება / გაყიდვა",
}


def _logo_b64() -> str:
    if not _LOGO_PATH.is_file():
        return ""
    return base64.b64encode(_LOGO_PATH.read_bytes()).decode()


def apply_watermark(b64_logo: str, opacity: float = 0.04) -> None:
    """Apply subtle logo watermark to page background."""
    if not b64_logo:
        return
    st.markdown(
        f"""
    <style>
    .watermark-bg {{
        position: fixed;
        top: 50%;
        left: 55%;
        transform: translate(-50%, -50%);
        width: 500px;
        height: 500px;
        background-image: url("data:image/png;base64,{b64_logo}");
        background-repeat: no-repeat;
        background-position: center;
        background-size: contain;
        opacity: {opacity};
        pointer-events: none;
        z-index: 0;
        filter: grayscale(40%) brightness(1.1);
    }}
    </style>
    <div class="watermark-bg"></div>
    """,
        unsafe_allow_html=True,
    )


PLOTLY_STREAMLIT_CONFIG: dict[str, object] = {
    "displayModeBar": False,
    "scrollZoom": False,
    "doubleClick": False,
    "modeBarButtonsToRemove": [
        "zoom2d",
        "pan2d",
        "select2d",
        "lasso2d",
        "zoomIn2d",
        "zoomOut2d",
        "autoScale2d",
        "resetScale2d",
        "zoom",
        "pan",
        "select",
        "zoomIn",
        "zoomOut",
        "autoScale",
        "resetScale",
    ],
}

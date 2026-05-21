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


def is_dark_mode() -> bool:
    """True when ``st.session_state.dark_mode`` is True (default)."""
    return bool(st.session_state.get("dark_mode", True))


def _theme_palette() -> dict[str, str]:
    """Runtime palette from ``st.session_state.dark_mode`` (authoritative)."""
    if is_dark_mode():
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
        "text": "#0F172A",
        "muted": "#94A3B8",
        "border": "#E2E8F0",
        "sidebar": "#FFFFFF",
        "input_bg": "#F8FAFC",
    }


_LIGHT_THEME_BASE_CSS = """
/* AT ANALYTICS — MODERN LIGHT THEME (2026) */
:root {
  --primary: #2563eb;
  --primary-hover: #1d4ed8;
  --primary-soft: #dbeafe;
  --accent: #06b6d4;
  --accent-soft: #cffafe;
  --success: #10b981;
  --warning: #f59e0b;
  --danger: #ef4444;
  --bg-main: #f4f7fb;
  --bg-sidebar: #ffffff;
  --bg-card: #ffffff;
  --bg-card-hover: #f9fbff;
  --bg-input: #f8fafc;
  --text-primary: #0f172a;
  --text-secondary: #475569;
  --text-muted: #94a3b8;
  --text-white: #ffffff;
  --border-color: #e2e8f0;
  --border-light: #f1f5f9;
  --shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.04);
  --shadow-md: 0 4px 12px rgba(15, 23, 42, 0.06);
  --shadow-lg: 0 10px 30px rgba(15, 23, 42, 0.10);
  --shadow-glow: 0 0 0 4px rgba(37, 99, 235, 0.10);
  --radius-sm: 10px;
  --radius-md: 16px;
  --radius-lg: 22px;
  --radius-xl: 28px;
  --transition: all 0.25s ease;
  --color-bg-main: #f4f7fb;
  --color-bg-card: #ffffff;
  --color-text-primary: #0f172a;
  --color-text-secondary: #475569;
  --color-border: #e2e8f0;
  --color-primary: #2563eb;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 24px;
  --font-numbers: "Space Grotesk", Inter, sans-serif;
}
html, body, .stApp {
  background: var(--bg-main) !important;
  color: var(--text-primary);
  font-family: Inter, sans-serif;
}
section[data-testid="stSidebar"] {
  background: var(--bg-sidebar) !important;
  border-right: 1px solid var(--border-light);
  box-shadow: var(--shadow-sm);
  color: var(--text-primary);
}
section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] small {
  color: var(--text-primary);
}
.dashboard-card, .metric-card {
  background: var(--bg-card) !important;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
  transition: var(--transition);
  padding: 22px;
}
.dashboard-card:hover, .metric-card:hover {
  transform: translateY(-4px);
  background: var(--bg-card-hover);
  box-shadow: var(--shadow-lg);
}
/* KPI HTML cards (components.css not loaded in light mode) */
.kpi-overview-row {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}
.kpi-overview-secondary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
}
.stat-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}
.stat-card {
  background: var(--bg-card) !important;
  border: 1px solid var(--border-light) !important;
  border-radius: var(--radius-lg) !important;
  padding: var(--space-5) !important;
  box-shadow: var(--shadow-md) !important;
  position: relative;
}
.stat-card::before {
  content: "";
  position: absolute;
  left: 0;
  top: 20px;
  bottom: 20px;
  width: 4px;
  background: var(--primary);
  border-radius: 0 8px 8px 0;
}
.stat-card {
  padding-left: calc(var(--space-5) + 4px) !important;
}
.stat-card--highlight {
  border-color: var(--primary) !important;
  background: var(--primary-soft) !important;
}
.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: var(--space-2);
  display: block;
}
.stat-value {
  font-family: var(--font-numbers);
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.1;
  display: block;
}
.stat-change {
  font-size: 14px;
  margin-top: var(--space-3);
  display: block;
}
.stat-change--success { color: var(--success); }
.stat-change--danger { color: var(--danger); }
.stat-change--warning { color: var(--warning); }
.stat-change--muted { color: #0284c7; }
.chart-panel {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  box-shadow: var(--shadow-md);
}
@media (max-width: 1024px) {
  .kpi-overview-row { grid-template-columns: 1fr; }
  .kpi-overview-secondary { grid-template-columns: repeat(2, 1fr); }
  .stat-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 768px) {
  .kpi-overview-secondary,
  .stat-grid { grid-template-columns: 1fr; }
}
h1, h2, h3, h4 {
  color: var(--text-primary);
  font-weight: 700;
  letter-spacing: -0.02em;
}
p, label, span {
  color: var(--text-secondary);
}
section[data-testid="stSidebar"] .stButton > button[kind="secondary"],
section[data-testid="stSidebar"] .stButton > button:not([kind="primary"]) {
  background: #f8fafc !important;
  color: #0f172a !important;
  box-shadow: none !important;
  border: 1px solid #e2e8f0 !important;
  border-radius: 14px !important;
  font-weight: 600;
  transition: var(--transition);
}
section[data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover,
section[data-testid="stSidebar"] .stButton > button:not([kind="primary"]):hover {
  background: #eff6ff !important;
  border-color: #bfdbfe !important;
  color: #0f172a !important;
}
section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
  background: linear-gradient(135deg, var(--primary), var(--accent)) !important;
  color: #ffffff !important;
  border: none !important;
  box-shadow: var(--shadow-md) !important;
}
section[data-testid="stSidebar"] .stButton > button[kind="primary"] *,
section[data-testid="stSidebar"] .stButton > button[kind="primary"] p,
section[data-testid="stSidebar"] .stButton > button[kind="primary"] span,
section[data-testid="stSidebar"] .stButton > button[kind="primary"] div {
  color: #ffffff !important;
}
section[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover,
section[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover * {
  color: #ffffff !important;
  filter: brightness(1.03);
}
section[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"],
section[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"] * {
  color: #ffffff !important;
}
section[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"] {
  background: linear-gradient(135deg, #2563eb, #06b6d4) !important;
  border: none !important;
}
section[data-testid="stSidebar"] div[data-testid="stVerticalBlockBorderWrapper"] > div,
section[data-testid="stSidebar"] [data-testid="stExpander"] {
  background: #ffffff !important;
  border: 1px solid #e2e8f0 !important;
  border-radius: 12px !important;
  color: #0f172a !important;
}
section[data-testid="stSidebar"] [data-testid="stExpander"] label,
section[data-testid="stSidebar"] [data-testid="stExpander"] p,
section[data-testid="stSidebar"] [data-testid="stExpander"] span,
section[data-testid="stSidebar"] [data-testid="stExpander"] .stMarkdown {
  color: #0f172a !important;
}
section.main .stButton > button,
[data-testid="stMain"] .stButton > button {
  background: linear-gradient(135deg, var(--primary), var(--accent));
  color: white !important;
  border: none;
  border-radius: 14px;
  padding: 12px 22px;
  font-weight: 600;
  transition: var(--transition);
  box-shadow: var(--shadow-sm);
}
section.main .stButton > button:hover,
[data-testid="stMain"] .stButton > button:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
  filter: brightness(1.03);
}
.stTextInput input, .stDateInput input,
.stSelectbox div[data-baseweb="select"] {
  background: var(--bg-input) !important;
  border: 1px solid var(--border-color) !important;
  border-radius: 14px !important;
  color: var(--text-primary) !important;
  transition: var(--transition);
}
.stTextInput input:focus, .stDateInput input:focus {
  border-color: var(--primary) !important;
  box-shadow: var(--shadow-glow) !important;
}
.chart-container {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 24px;
  border: 1px solid var(--border-light);
  box-shadow: var(--shadow-md);
}
table {
  border-radius: 16px !important;
  overflow: hidden;
  border: 1px solid var(--border-light);
}
thead tr { background: #eff6ff !important; }
thead th {
  color: var(--primary) !important;
  font-weight: 700 !important;
}
tbody tr { transition: var(--transition); }
tbody tr:hover { background: #f8fbff !important; }
.kpi-success { color: var(--success); }
.kpi-danger { color: var(--danger); }
.kpi-warning { color: var(--warning); }
.ai-alert {
  background: linear-gradient(135deg, #eff6ff, #ecfeff);
  border: 1px solid #bfdbfe;
  color: var(--text-primary);
  border-radius: 18px;
  padding: 18px 22px;
  box-shadow: var(--shadow-sm);
}
.nav-button {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 14px;
  transition: var(--transition);
  padding: 14px 18px;
}
.nav-button:hover {
  background: #eff6ff;
  border-color: #bfdbfe;
}
.nav-button.active {
  background: linear-gradient(135deg, var(--primary), var(--accent));
  color: white !important;
  box-shadow: var(--shadow-md);
}
::-webkit-scrollbar { width: 10px; }
::-webkit-scrollbar-track { background: #edf2f7; }
::-webkit-scrollbar-thumb {
  background: linear-gradient(var(--primary), var(--accent));
  border-radius: 999px;
}
.glass {
  background: rgba(255, 255, 255, 0.75);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.5);
}
.main::before {
  content: "";
  position: fixed;
  inset: 0;
  background:
    radial-gradient(circle at top right, rgba(37, 99, 235, 0.05), transparent 30%),
    radial-gradient(circle at bottom left, rgba(6, 182, 212, 0.05), transparent 30%);
  pointer-events: none;
  z-index: 0;
}
"""


def _runtime_theme_css_light() -> str:
    """Light-mode Streamlit overrides (2026 SaaS design system)."""
    return """
html, body, .stApp, [data-testid="stAppViewContainer"] {
  background: #f4f7fb !important;
  color: #0f172a !important;
}
[data-testid="stHeader"] {
  height: 0 !important;
  visibility: hidden !important;
}
section[data-testid="stSidebar"] {
  background: #ffffff !important;
  border-right: 1px solid #f1f5f9 !important;
}
section[data-testid="stSidebar"] .stButton > button[kind="secondary"],
section[data-testid="stSidebar"] .stButton > button:not([kind="primary"]) {
  background: #f8fafc !important;
  color: #0f172a !important;
  box-shadow: none !important;
  border: 1px solid #e2e8f0 !important;
  border-radius: 14px !important;
  font-weight: 600;
}
section[data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover,
section[data-testid="stSidebar"] .stButton > button:not([kind="primary"]):hover {
  background: #eff6ff !important;
  border-color: #bfdbfe !important;
  color: #0f172a !important;
}
section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
  background: linear-gradient(135deg, #2563eb, #06b6d4) !important;
  color: #ffffff !important;
  border: none !important;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06) !important;
}
section[data-testid="stSidebar"] .stButton > button[kind="primary"] *,
section[data-testid="stSidebar"] .stButton > button[kind="primary"] p,
section[data-testid="stSidebar"] .stButton > button[kind="primary"] span,
section[data-testid="stSidebar"] .stButton > button[kind="primary"] div {
  color: #ffffff !important;
}
section[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover,
section[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover * {
  color: #ffffff !important;
  filter: brightness(1.03);
}
section[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"],
section[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"] * {
  color: #ffffff !important;
}
section[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"] {
  background: linear-gradient(135deg, #2563eb, #06b6d4) !important;
  border: none !important;
}
section[data-testid="stSidebar"] div[data-testid="stVerticalBlockBorderWrapper"] > div,
section[data-testid="stSidebar"] [data-testid="stExpander"] {
  background: #ffffff !important;
  border: 1px solid #e2e8f0 !important;
  border-radius: 12px !important;
  color: #0f172a !important;
}
section[data-testid="stSidebar"] [data-testid="stExpander"] label,
section[data-testid="stSidebar"] [data-testid="stExpander"] p,
section[data-testid="stSidebar"] [data-testid="stExpander"] span,
section[data-testid="stSidebar"] [data-testid="stExpander"] .stMarkdown,
section[data-testid="stSidebar"] [data-testid="stExpander"] small {
  color: #0f172a !important;
}
section[data-testid="stSidebar"] [data-testid="stDateInput"] label {
  color: #475569 !important;
}
section[data-testid="stSidebar"] details,
section[data-testid="stSidebar"] details > summary {
  background: #ffffff !important;
  color: #0f172a !important;
}
section[data-testid="stSidebar"] details summary {
  background: #f8fafc !important;
  border: 1px solid #e2e8f0 !important;
  border-radius: 10px !important;
}
[data-testid="block-container"] {
  padding-top: 1rem !important;
}
div[data-testid="stPlotlyChart"] {
  background: #ffffff !important;
  border-radius: 16px !important;
  border: 1px solid #f1f5f9 !important;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06) !important;
}
section.main .stButton > button,
[data-testid="stMain"] .stButton > button {
  background: linear-gradient(135deg, #2563eb, #06b6d4) !important;
  color: #ffffff !important;
}
.stMarkdown, .stMarkdown p, .stMarkdown li, .stMarkdown span,
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3, label, .main-title,
.card, .at-card, .stat-card, .hero-card {
  color: #0f172a !important;
}
.subtitle, .stat-label {
  color: #475569 !important;
}
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stDateInput"] input {
  background: #f8fafc !important;
  color: #0f172a !important;
  border: 1px solid #e2e8f0 !important;
}
"""


def _runtime_theme_css_dark(palette: dict[str, str]) -> str:
    """Dark-mode direct overrides (unchanged)."""
    t = palette["name"]
    bg, card, text = palette["bg"], palette["card"], palette["text"]
    muted, border = palette["muted"], palette["border"]
    sidebar, input_bg = palette["sidebar"], palette["input_bg"]
    color_scheme = "dark" if t == "dark" else "light"
    return f"""
html, body {{
  color-scheme: {color_scheme};
}}
:root {{
  --color-bg-main: {bg};
  --color-bg-secondary: {card};
  --color-bg-card: {card};
  --color-bg-soft: {card};
  --color-text-primary: {text};
  --color-text-secondary: {muted};
  --color-border: {border};
  --color-gradient-main: {bg};
}}
.stApp,
body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
section.main,
.main {{
  background-color: {bg} !important;
  color: {text} !important;
}}
.card,
.at-card,
.stat-card,
.hero-card,
.card-glass,
.ai-box,
div[data-testid="stMetric"],
[data-testid="stMetric"] {{
  background-color: {card} !important;
  color: {text} !important;
  border-color: {border} !important;
}}
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div {{
  background-color: {sidebar} !important;
  color: {text} !important;
}}
[data-testid="stSidebar"] * {{
  color: {text};
}}
.stMarkdown,
.stMarkdown p,
.stMarkdown li,
.stMarkdown span,
.stMarkdown h1,
.stMarkdown h2,
.stMarkdown h3,
label,
.main-title {{
  color: {text} !important;
}}
.subtitle,
.stat-label {{
  color: {muted} !important;
}}
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stDateInput"] input {{
  background-color: {input_bg} !important;
  color: {text} !important;
  border-color: {border} !important;
}}
[data-testid="stHeader"] {{
  background-color: {bg} !important;
}}
"""


def _runtime_theme_css(palette: dict[str, str]) -> str:
    """Runtime CSS from current palette."""
    if palette["name"] == "light":
        return _runtime_theme_css_light()
    return _runtime_theme_css_dark(palette)


def apply_theme_css() -> None:
    """
    Inject theme on every rerun from ``st.session_state.dark_mode``.
    Static CSS files load first; runtime block overrides backgrounds/text.
    """
    if "dark_mode" not in st.session_state:
        st.session_state.dark_mode = True
    st.session_state["theme"] = get_theme_name()
    palette = _theme_palette()
    if is_dark_mode():
        design_css = load_design_css()
    else:
        design_css = _LIGHT_THEME_BASE_CSS
    st.markdown(
        f"""
        <style>
        @import url('{GOOGLE_FONTS_URL}');
        {design_css}
        {_runtime_theme_css(palette)}
        </style>
        """,
        unsafe_allow_html=True,
    )


def is_light_mode() -> bool:
    """True when light theme is active (``dark_mode`` is False)."""
    return not is_dark_mode()


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
    if is_dark_mode():
        paper_bg = "#0F172A"
        plot_bg = "#0F172A"
        text_color = "#F1F5F9"
        grid_color = "#1E293B"
        hover_bg = "#151F32"
    else:
        paper_bg = "#FFFFFF"
        plot_bg = "#F4F7FB"
        text_color = "#1E293B"
        grid_color = "#E2E8F0"
        hover_bg = "#FFFFFF"

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

    pie_line = "#FFFFFF" if not is_dark_mode() else "#0F172A"
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

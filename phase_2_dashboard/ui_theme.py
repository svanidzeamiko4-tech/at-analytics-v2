"""Shared UI tokens — Modern SaaS Distribution Analytics design system."""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

_LOGO_PATH = Path(__file__).resolve().parent / "assets" / "at_analytics_logo.png"

# --- Design system palette ---
PRIMARY = "#00D1C7"
PRIMARY_DARK = "#00A8A0"
ACCENT = "#7C3AED"
BG = "#0B1220"
CARD = "#111827"
CARD_HOVER = "#1F2937"
BORDER = "#1E293B"
TEXT = "#E5E7EB"
MUTED = "#9CA3AF"
SUCCESS = "#10B981"
WARNING = "#F59E0B"
DANGER = "#EF4444"

PRIMARY_GLOW = "rgba(0, 209, 199, 0.35)"
PRIMARY_DIM = "rgba(0, 209, 199, 0.12)"
ACCENT_DIM = "rgba(124, 58, 237, 0.14)"
SUCCESS_DIM = "rgba(16, 185, 129, 0.14)"

RADIUS = "16px"
CARD_PADDING = "24px"

FONT_HEADING = "'Sora', 'Inter', system-ui, sans-serif"
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
    "family=Sora:wght@600;700&"
    "family=Space+Grotesk:wght@500;600;700&display=swap"
)

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

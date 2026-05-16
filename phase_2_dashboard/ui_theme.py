"""Shared UI tokens and Georgian copy (no app imports)."""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

_LOGO_PATH = Path(__file__).resolve().parent / "assets" / "at_analytics_logo.png"

BG = "#0e1117"
CARD = "#1a1c24"
BORDER = "#2d303a"
TEXT = "#f0f2f6"
MUTED = "#9aa0ab"
PAGE_SUB = "#6b7280"
NEON_BLUE = "#22d3ee"
NEON_BLUE_DIM = "rgba(34, 211, 238, 0.14)"
HEADER_NEON_CYAN = "#00FFFF"
EMERALD = "#34d399"
EMERALD_DIM = "rgba(52, 211, 153, 0.14)"
RED_RET = "#f87171"
GRID = "#2a2d38"
FONT_FAMILY = "'BPG Nino Mtavruli', 'Segoe UI', 'Inter', system-ui, sans-serif"

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
        filter: grayscale(30%);
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

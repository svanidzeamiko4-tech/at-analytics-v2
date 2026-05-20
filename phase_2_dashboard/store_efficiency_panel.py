"""
მაღაზიის return-rate ანალიტიკა: KPI (საუკეთესო/პრობლემური/საშუალო), ჰორიზონტალური ბარი, heatmap სლოტი.
გამოიყენება ``phase_2_dashboard/app.py`` (მთავარი საიტი).
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

from charts.store_charts import return_rate_chart
from data_loader import returns_vs_sales_by_store

_PLOTLY_CFG: dict = {"displayModeBar": False}
from ui_theme import BG, BORDER, CARD_HOVER, FONT_BODY, MUTED, PRIMARY, SUCCESS, TEXT

_FONT = FONT_BODY
_CARD_MUTED = MUTED
_TEXT = TEXT
_BRAND_MINT = SUCCESS
_TABLE_BG = BG
_TABLE_ROW_HOVER = CARD_HOVER
_TABLE_TEXT = TEXT

_STORE_DETAIL_UI_CSS = f"""
<style>
/* დეტალური ცხრილი — expander (dark + brand border) */
div[data-testid="stExpander"] > div > details {{
  background-color: {_TABLE_BG} !important;
  border: 1px solid {PRIMARY} !important;
  border-radius: 12px !important;
  overflow: hidden;
}}
/* Summary: centered label; hide broken Material chevron (literal "arrow_drop_down") */
div[data-testid="stExpander"] summary {{
  background-color: #161b22 !important;
  color: #f1f5f9 !important;
  list-style: none;
  display: flex !important;
  flex-direction: row;
  align-items: center !important;
  justify-content: center !important;
  gap: 0.45rem;
  padding: 0.65rem 0.75rem !important;
  margin: 0 !important;
}}
div[data-testid="stExpander"] summary::-webkit-details-marker {{
  display: none !important;
}}
div[data-testid="stExpander"] summary::marker {{
  content: "";
}}
div[data-testid="stExpander"] summary [data-testid="stIconMaterial"] {{
  display: none !important;
  width: 0 !important;
  height: 0 !important;
  overflow: hidden !important;
  position: absolute !important;
  clip: rect(0, 0, 0, 0) !important;
  margin: 0 !important;
  padding: 0 !important;
  border: 0 !important;
}}
div[data-testid="stExpander"] summary::before {{
  content: "▼";
  font-size: 0.62rem;
  color: #94a3b8;
  flex-shrink: 0;
  line-height: 1;
  font-family: system-ui, "Segoe UI", sans-serif;
}}
div[data-testid="stExpander"] details[open] > summary::before {{
  content: "▲";
  font-size: 0.55rem;
}}
div[data-testid="stExpander"] summary span,
div[data-testid="stExpander"] summary p {{
  color: #f1f5f9 !important;
  font-family: {_FONT};
  text-align: center;
  margin: 0 !important;
}}
div[data-testid="stExpander"] [data-testid="stExpanderDetails"],
div[data-testid="stExpander"] [data-testid="stExpanderContent"] {{
  background-color: {_TABLE_BG} !important;
  border-top: 1px solid rgba(0, 180, 216, 0.25);
  padding: 0.35rem 0.5rem 0.65rem 0.5rem !important;
}}
div[data-testid="stExpander"] [data-testid="stExpanderDetails"] > div,
div[data-testid="stExpander"] [data-testid="stExpanderContent"] > div {{
  background-color: transparent !important;
}}
/* HTML table from pandas Styler (avoids Glide st.dataframe white strip / light header) */
.store-detail-table-frame {{
  background: transparent !important;
  margin: 0 !important;
  padding: 0 !important;
  width: 100%;
}}
.store-detail-table-frame table#T_store_dm {{
  width: 100%;
  background-color: {_TABLE_BG} !important;
  border-collapse: collapse;
  margin: 0 !important;
}}
.store-detail-table-frame table#T_store_dm thead th {{
  background-color: {_BRAND_MINT} !important;
  color: {BG} !important;
  font-family: {_FONT} !important;
}}
.store-detail-table-frame table#T_store_dm tbody td {{
  font-family: {_FONT} !important;
}}
.store-detail-table-frame table#T_store_dm tbody tr:hover td {{
  background-color: {_TABLE_ROW_HOVER} !important;
}}
/* Streamlit markdown wrapper inside expander — kill default light padding/background */
div[data-testid="stExpanderDetails"] div[data-testid="stMarkdownContainer"] {{
  background: transparent !important;
  padding-bottom: 0 !important;
}}
div[data-testid="stExpanderDetails"] div[data-testid="stMarkdownContainer"] > div {{
  background: transparent !important;
}}
/* Legacy: any st.dataframe left in this block */
div[data-testid="stDataFrame"],
div[data-testid="stDataFrame"] > div {{
  background-color: transparent !important;
}}
div[data-testid="stDataFrame"] [class*="glide"],
div[data-testid="stDataFrame"] [class*="dvn"] {{
  background-color: {_TABLE_BG} !important;
}}
</style>
"""


def _return_rate_pct_cell_css(value: object) -> str:
    """Red if >30%, green if <10%; mid stays on dark base."""
    if pd.isna(value):
        return ""
    try:
        x = float(value)
    except (TypeError, ValueError):
        return ""
    if x > 30:
        return "background-color: rgba(239, 68, 68, 0.38); color: #fecaca; font-weight: 600;"
    if x < 10:
        return "background-color: rgba(34, 197, 94, 0.32); color: #bbf7d0; font-weight: 600;"
    return f"background-color: {_TABLE_BG}; color: {_TABLE_TEXT};"


def _style_store_metrics_table(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    """Dark table + neon header + return_rate_pct heat hints (for st.dataframe)."""
    if df.empty:
        return df.style.hide(axis="index")

    thead = {
        "selector": "thead th",
        "props": [
            ("background-color", _BRAND_MINT),
            ("color", BG),
            ("font-weight", "600"),
            ("font-family", _FONT),
            ("border", "1px solid rgba(14, 17, 23, 0.35)"),
            ("padding", "10px 8px"),
        ],
    }
    tbody_cell = {
        "selector": "tbody td",
        "props": [
            ("border", "1px solid rgba(255,255,255,0.06)"),
            ("padding", "8px"),
        ],
    }
    row_hover = {
        "selector": "tbody tr:hover td",
        "props": [("background-color", _TABLE_ROW_HOVER)],
    }

    def _pct_col_styles(series: pd.Series) -> list[str]:
        return [_return_rate_pct_cell_css(v) for v in series]

    return (
        df.style.format(
            {"sales_gel": "{:,.1f}", "returns_gel": "{:,.1f}", "return_rate_pct": "{:.2f}"},
            na_rep="—",
        )
        .set_table_styles([thead, tbody_cell, row_hover], overwrite=False)
        .set_properties(
            **{
                "background-color": _TABLE_BG,
                "color": _TABLE_TEXT,
                "font-family": _FONT,
            },
        )
        .apply(_pct_col_styles, axis=0, subset=["return_rate_pct"])
        .hide(axis="index")
    )


def calculate_store_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    აჯგუფებს მაღაზიის მიხედვით და ითვლის:
    ``sales_gel``, ``returns_gel``, ``return_rate_pct`` = (Returns / Sales) * 100.
    """
    if df is None or df.empty:
        return pd.DataFrame(
            columns=["store_name", "sales_gel", "returns_gel", "return_rate_pct"]
        )
    d = df.copy()
    if "store_name" not in d.columns and "store_display_name" in d.columns:
        d = d.rename(columns={"store_display_name": "store_name"})
    if "store_name" not in d.columns:
        return pd.DataFrame(
            columns=["store_name", "sales_gel", "returns_gel", "return_rate_pct"]
        )

    sales_col = "sales_gel" if "sales_gel" in d.columns else None
    ret_col = "returns_gel" if "returns_gel" in d.columns else None
    if sales_col is None or ret_col is None:
        return pd.DataFrame(
            columns=["store_name", "sales_gel", "returns_gel", "return_rate_pct"]
        )

    g = d.groupby("store_name", as_index=False).agg(
        sales_gel=(sales_col, "sum"),
        returns_gel=(ret_col, "sum"),
    )
    sales = g["sales_gel"].astype(float)
    ret = g["returns_gel"].astype(float).clip(lower=0.0)
    rate = np.where(sales > 1e-9, (ret / sales) * 100.0, np.nan)
    g["return_rate_pct"] = np.round(rate, 2)
    g["sales_gel"] = sales.round(2)
    g["returns_gel"] = ret.round(2)
    return g.sort_values("return_rate_pct", ascending=False, na_position="last")


def _truncate(s: str, n: int = 36) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def render_store_efficiency_section(
    invoices: pd.DataFrame,
    lines: pd.DataFrame,
    d_start: date,
    d_end: date,
) -> None:
    st.subheader("მაღაზია · დაბრუნების კოეფიციენტი")
    raw = returns_vs_sales_by_store(invoices, lines, d_start, d_end)
    m = calculate_store_metrics(raw)
    if m.empty:
        st.info("ამ პერიოდში მონაცემები არ არის.")
        return

    valid = m["sales_gel"].astype(float) > 1e-6
    m_valid = m.loc[valid].copy()
    total_sales = float(m["sales_gel"].sum())
    total_returns = float(m["returns_gel"].sum())
    net_avg = (total_returns / total_sales * 100.0) if total_sales > 1e-9 else 0.0

    c1, c2, c3 = st.columns(3)
    if not m_valid.empty:
        best = m_valid.nsmallest(1, "return_rate_pct").iloc[0]
        worst = m_valid.nlargest(1, "return_rate_pct").iloc[0]
        with c1:
            st.metric(
                "საუკეთესო მაღაზია",
                _truncate(str(best["store_name"]), 28),
                delta=f"{float(best['return_rate_pct']):.2f}% return rate",
                delta_color="normal",
                help="ყველაზე დაბალი Return Rate (Sales > 0)",
            )
        with c2:
            st.metric(
                "პრობლემური მაღაზია",
                _truncate(str(worst["store_name"]), 28),
                delta=f"{float(worst['return_rate_pct']):.2f}% return rate",
                delta_color="inverse",
                help="ყველაზე მაღალი Return Rate (Sales > 0)",
            )
    else:
        with c1:
            st.metric("საუკეთესო მაღაზია", "—", help="არ არის მაღაზია დადებითი გაყიდვით")
        with c2:
            st.metric("პრობლემური მაღაზია", "—", help="არ არის მაღაზია დადებითი გაყიდვით")

    with c3:
        st.metric(
            "საშუალო დაბრუნების კოეფიციენტი (ქსელი)",
            f"{net_avg:.2f}%",
            help="(ჯამური დაბრუნებები / ჯამური გაყიდვები) × 100",
        )

    st.plotly_chart(
        return_rate_chart(m),
        use_container_width=True,
        config=_PLOTLY_CFG,
        key="store_return_rate_hbar",
    )

    with st.expander("დეტალური ცხრილი (მაღაზია)", expanded=False):
        st.markdown(_STORE_DETAIL_UI_CSS, unsafe_allow_html=True)
        _html = (
            '<div class="store-detail-table-frame">'
            + _style_store_metrics_table(m).to_html(table_uuid="store_dm", border=0)
            + "</div>"
        )
        st.html(_html, width="stretch")

    st.info("Heatmap by Hour/Day coming soon")

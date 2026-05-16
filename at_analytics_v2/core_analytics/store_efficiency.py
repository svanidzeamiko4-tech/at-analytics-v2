"""
პუნქტი 3: მაღაზიის ეფექტურობა — დაბრუნების კოეფიციენტი, KPI და ჰორიზონტალური ბარი.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .data_bridge import ensure_phase2_import_path

_PLOTLY_CFG: dict = {"displayModeBar": False}

# KPI / ჩარტი — მუქი თემასთან შესაბამისი
_CARD_MUTED = "#9aa0ab"
_TEXT = "#f0f2f6"
_GRID = "rgba(255,255,255,0.08)"


def return_rate_by_store(
    invoices: pd.DataFrame,
    lines: pd.DataFrame,
    start: date,
    end: date,
) -> pd.DataFrame:
    ensure_phase2_import_path()
    import data_loader as dl  # noqa: E402

    return dl.returns_vs_sales_by_store(invoices, lines, start, end)


def calculate_store_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    აჯგუფებს მაღაზიის მიხედვით (თუ რამდენიმე ხაზია ერთ სახელზე — ჯამდება) და ითვლის:
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

    g = (
        d.groupby("store_name", as_index=False)
        .agg(sales_gel=(sales_col, "sum"), returns_gel=(ret_col, "sum"))
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


def _return_rate_bar_chart(m: pd.DataFrame) -> go.Figure:
    """ჰორიზონტალური ბარი: Return Rate %; ფერი მწვანიდან წითელამდე (მაღალი = „საშიში“)."""
    fig = go.Figure()
    if m.empty or m["return_rate_pct"].isna().all():
        fig.add_annotation(
            text="მონაცემები არ არის",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(color=_CARD_MUTED, size=14),
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=_TEXT, size=12),
            height=220,
            margin=dict(t=40, b=40, l=8, r=24),
        )
        return fig

    plot_df = m.dropna(subset=["return_rate_pct"]).copy()
    if plot_df.empty:
        return _return_rate_bar_chart(pd.DataFrame())

    plot_df = plot_df.sort_values("return_rate_pct", ascending=True)
    rr = plot_df["return_rate_pct"].astype(float)
    lo, hi = float(rr.min()), float(rr.max())
    if hi - lo < 1e-6:
        cmin, cmax = lo - 0.5, hi + 0.5
    else:
        cmin, cmax = lo, hi

    ylabs = plot_df["store_name"].map(lambda x: _truncate(str(x), 42))
    fig.add_trace(
        go.Bar(
            orientation="h",
            y=ylabs,
            x=plot_df["return_rate_pct"],
            marker=dict(
                color=plot_df["return_rate_pct"],
                colorscale=[[0.0, "#22c55e"], [0.5, "#eab308"], [1.0, "#ef4444"]],
                cmin=cmin,
                cmax=cmax,
                line=dict(width=0),
                showscale=True,
                colorbar=dict(
                    title=dict(text="%", side="right"),
                    tickfont=dict(size=10, color=_CARD_MUTED),
                ),
            ),
            text=plot_df["return_rate_pct"].map(lambda v: f"{v:.1f}%"),
            textposition="outside",
            textfont=dict(size=10, color=_CARD_MUTED),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Return rate: %{x:.2f}%<br>"
                "გაყიდვები: %{customdata[1]:,.2f} GEL<br>"
                "დაბრუნება: %{customdata[2]:,.2f} GEL<extra></extra>"
            ),
            customdata=np.column_stack(
                [
                    plot_df["store_name"].astype(str),
                    plot_df["sales_gel"].astype(float),
                    plot_df["returns_gel"].astype(float),
                ]
            ),
        )
    )
    n = len(plot_df)
    h = min(720, max(260, 28 * n + 100))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=_TEXT, size=12),
        height=h,
        margin=dict(t=48, b=48, l=8, r=120),
        title=dict(
            text="Return Rate % — მაღაზიები (დაბალი → მაღალი, ზემოთ უფრო „ცხელი“)",
            font=dict(size=14, color=_TEXT),
            x=0,
            xanchor="left",
        ),
        xaxis=dict(
            title="Return rate (%)",
            gridcolor=_GRID,
            zeroline=True,
            zerolinecolor=_GRID,
            tickfont=dict(size=10, color=_CARD_MUTED),
        ),
        yaxis=dict(
            title="",
            automargin=True,
            tickfont=dict(size=10, color=_CARD_MUTED),
        ),
    )
    return fig


def render_tab(
    invoices: pd.DataFrame,
    lines: pd.DataFrame,
    d_start: date,
    d_end: date,
) -> None:
    st.subheader("მაღაზია · დაბრუნების კოეფიციენტი")
    raw = return_rate_by_store(invoices, lines, d_start, d_end)
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
        _return_rate_bar_chart(m),
        use_container_width=True,
        config=_PLOTLY_CFG,
    )

    with st.expander("დეტალური ცხრილი (მაღაზია)", expanded=False):
        st.dataframe(m, use_container_width=True, hide_index=True)

    st.info("Heatmap by Hour/Day coming soon")

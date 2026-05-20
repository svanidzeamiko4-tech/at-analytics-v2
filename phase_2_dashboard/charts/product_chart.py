"""Top products horizontal bar — clean labels, mobile-friendly."""

from __future__ import annotations

import re

import pandas as pd
import plotly.graph_objects as go

from ui_theme import ACCENT, PRIMARY, plotly_axis_style

CHART_PRIMARY = PRIMARY
CHART_ACCENT = ACCENT


def _clean_product_name(name: str) -> str:
    s = str(name or "").strip()
    s = re.sub(r"^\|?\s*\d+\s*\|\s*", "", s)
    s = re.sub(r"^\d+\.\s*", "", s)
    return s.strip()


def _extract_product_name(label: str) -> str:
    s = str(label or "").strip()
    if " · " in s:
        s = s.split(" · ", 1)[1].strip()
    elif "·" in s:
        s = s.rsplit("·", 1)[1].strip()
    return _clean_product_name(s)


def top_products_chart(df: pd.DataFrame, top_n: int = 15) -> go.Figure:
    fig = go.Figure()
    if df.empty:
        fig.add_annotation(
            text="მონაცემი არ არის",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
        )
        fig.update_layout(height=300)
        return fig

    label_col = "product_label" if "product_label" in df.columns else df.columns[0]
    d = df.copy()
    d["product"] = d[label_col].map(_extract_product_name)
    d = (
        d.groupby("product", as_index=False)
        .agg(quantity=("quantity", "sum"), sales_gel=("sales_gel", "sum"))
        .sort_values("quantity", ascending=True)
        .tail(top_n)
    )
    n = len(d)
    h = max(300, n * 36)

    max_q = float(d["quantity"].max()) or 1
    colors = [
        f"rgba({int(0 + 17 * q / max_q)},{int(180 - 69 * q / max_q)},{int(216 - 56 * q / max_q)},0.9)"
        for q in d["quantity"]
    ]

    fig.add_trace(
        go.Bar(
            orientation="h",
            y=d["product"],
            x=d["quantity"],
            marker=dict(color=colors, line=dict(width=0), cornerradius=6),
            customdata=d[["sales_gel"]].values,
            hovertemplate=(
                "<b>%{y}</b><br>"
                "რაოდენობა: <b>%{x:,.0f} ც</b><br>"
                "გაყიდვა: <b>%{customdata[0]:,.0f} ₾</b>"
                "<extra></extra>"
            ),
            texttemplate="%{x:,.0f}",
            textposition="outside",
            textfont=dict(size=10),
        )
    )
    axis = plotly_axis_style()
    fig.update_layout(
        height=h,
        margin=dict(l=10, r=50, t=30, b=20),
        title=dict(
            text=f"ტოპ {top_n} პროდუქტი (რაოდენობა)",
            font=dict(size=13),
            x=0.5,
            xanchor="center",
        ),
        xaxis=dict(**axis, zeroline=False),
        yaxis=dict(automargin=True, showgrid=False),
        showlegend=False,
        dragmode=False,
    )
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig

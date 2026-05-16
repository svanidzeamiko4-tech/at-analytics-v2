"""Top products horizontal bar — clean labels, mobile-friendly."""

from __future__ import annotations

import re

import pandas as pd
import plotly.graph_objects as go

TEXT = "#f0f2f6"
MUTED = "#9aa0ab"
FONT = "'BPG Nino Mtavruli','Segoe UI',system-ui,sans-serif"
GRID = "rgba(255,255,255,0.05)"


def _clean_product_name(name: str) -> str:
    """
    Remove OCR table artifacts:
    '| 6 | სენდვიჩ ტოსტი' → 'სენდვიჩ ტოსტი'
    '| 38 | პეროგი' → 'პეროგი'
    '3 | კულიჩი' → 'კულიჩი'
    """
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
    """
    Horizontal bars — product name only (no store prefix).
    Groups by product across all stores.
    """
    fig = go.Figure()
    if df.empty:
        fig.add_annotation(
            text="მონაცემი არ არის",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(color=MUTED),
        )
        fig.update_layout(
            height=300,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
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
            marker=dict(color=colors, line=dict(width=0)),
            customdata=d[["sales_gel"]].values,
            hovertemplate=(
                "<b>%{y}</b><br>"
                "რაოდენობა: <b>%{x:,.0f} ც</b><br>"
                "გაყიდვა: <b>%{customdata[0]:,.0f} ₾</b>"
                "<extra></extra>"
            ),
            texttemplate="%{x:,.0f}",
            textposition="outside",
            textfont=dict(color=MUTED, size=10),
        )
    )
    fig.update_layout(
        height=h,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT, family=FONT, size=10),
        margin=dict(l=10, r=50, t=30, b=20),
        title=dict(
            text=f"ტოპ {top_n} პროდუქტი (რაოდენობა)",
            font=dict(size=13, color=TEXT),
            x=0.5,
            xanchor="center",
        ),
        xaxis=dict(
            gridcolor=GRID,
            zeroline=False,
            tickfont=dict(size=9, color=MUTED),
        ),
        yaxis=dict(
            automargin=True,
            showgrid=False,
            tickfont=dict(size=10, color=TEXT),
        ),
        showlegend=False,
        dragmode=False,
    )
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig

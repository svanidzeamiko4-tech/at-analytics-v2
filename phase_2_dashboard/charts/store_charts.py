"""Store donut + bar charts — mobile-first, readable labels."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ui_theme import (
    ACCENT,
    BG,
    BORDER,
    FONT_BODY,
    MUTED,
    PRIMARY,
    PRIMARY_DARK,
    SUCCESS,
    TEXT,
)

BRAND_CYAN = PRIMARY
BRAND_MINT = SUCCESS
FONT = FONT_BODY
GRID = BORDER
COLORS = [
    PRIMARY,
    SUCCESS,
    PRIMARY_DARK,
    ACCENT,
    "#0d9488",
    "#059669",
    "#6366f1",
    "#14b8a6",
    "#10b981",
    "#7c3aed",
]


def _short(text: str, n: int = 18) -> str:
    s = str(text).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def store_donut(df: pd.DataFrame) -> go.Figure:
    """Compact donut — TOP 10 slices + «სხვა» bucket."""
    fig = go.Figure()
    if df.empty or float(df["revenue_gel"].sum()) <= 0:
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

    d = df.nlargest(10, "revenue_gel").copy()
    other_sum = float(df["revenue_gel"].sum()) - float(d["revenue_gel"].sum())
    if other_sum > 0:
        other_row = pd.DataFrame(
            [{"store_name": "სხვა მაღაზიები", "revenue_gel": other_sum}]
        )
        d = pd.concat([d, other_row], ignore_index=True)

    labels = d["store_name"].map(lambda x: _short(x, 20))
    fig.add_trace(
        go.Pie(
            labels=labels,
            values=d["revenue_gel"],
            hole=0.55,
            textinfo="percent",
            textposition="inside",
            textfont=dict(size=10, color=TEXT),
            marker=dict(
                colors=COLORS * (len(d) // len(COLORS) + 1),
                line=dict(color=BG, width=1.5),
            ),
            hovertemplate="<b>%{label}</b><br>%{value:,.0f} ₾ (%{percent})<extra></extra>",
        )
    )
    fig.update_layout(
        height=320,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT, family=FONT, size=10),
        margin=dict(l=0, r=0, t=30, b=100),
        title=dict(
            text="შემოსავლის წილი (%)",
            font=dict(size=13, color=TEXT),
            x=0.5,
            xanchor="center",
        ),
        legend=dict(
            orientation="h",
            x=0.5,
            xanchor="center",
            y=-0.25,
            yanchor="top",
            font=dict(size=9, color=TEXT),
            bgcolor="rgba(0,0,0,0)",
        ),
        dragmode=False,
    )
    fig.update_traces(domain=dict(x=[0.05, 0.95], y=[0.15, 1.0]))
    return fig


def sales_returns_bar(df: pd.DataFrame) -> go.Figure:
    """
    Horizontal bar chart — store names readable on mobile.
    Shows TOP 15 stores by sales.
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

    d = (
        df.nlargest(15, "sales_gel")
        .assign(
            sales_gel=lambda x: pd.to_numeric(x["sales_gel"], errors="coerce").fillna(0),
            returns_gel=lambda x: pd.to_numeric(x["returns_gel"], errors="coerce")
            .fillna(0)
            .clip(lower=0),
        )
        .sort_values("sales_gel", ascending=True)
        .reset_index(drop=True)
    )
    ys = d["store_name"].map(lambda x: _short(x, 25))
    n = len(d)
    h = max(320, n * 38)

    fig.add_trace(
        go.Bar(
            name="გაყიდვები",
            y=ys,
            x=d["sales_gel"],
            orientation="h",
            marker=dict(color=BRAND_CYAN, line=dict(width=0)),
            hovertemplate="<b>%{y}</b><br>გაყიდვები: %{x:,.0f} ₾<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            name="დაბრუნება",
            y=ys,
            x=d["returns_gel"],
            orientation="h",
            marker=dict(color=BRAND_MINT, line=dict(width=0)),
            hovertemplate="<b>%{y}</b><br>დაბრუნება: %{x:,.0f} ₾<extra></extra>",
        )
    )
    fig.update_layout(
        height=h,
        barmode="group",
        bargap=0.25,
        bargroupgap=0.1,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT, family=FONT, size=10),
        margin=dict(l=10, r=60, t=30, b=60),
        title=dict(
            text="გაყიდვები vs დაბრუნება (ტოპ 15)",
            font=dict(size=13, color=TEXT),
            x=0.5,
            xanchor="center",
        ),
        legend=dict(
            orientation="h",
            x=0.5,
            xanchor="center",
            y=-0.1,
            yanchor="top",
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11),
        ),
        xaxis=dict(
            gridcolor=GRID,
            zeroline=True,
            tickformat=",.0f",
            ticksuffix=" ₾",
            tickfont=dict(size=9, color=MUTED),
        ),
        yaxis=dict(
            automargin=True,
            showgrid=False,
            tickfont=dict(size=10, color=TEXT),
        ),
        dragmode=False,
    )
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def return_rate_chart(df: pd.DataFrame) -> go.Figure:
    """Horizontal bar — return rate by store, TOP 20 only."""
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

    d = df.copy()
    if "return_pct" not in d.columns and "return_rate_pct" in d.columns:
        d["return_pct"] = d["return_rate_pct"]
    if "return_pct" not in d.columns or d["return_pct"].isna().all():
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

    d = d.dropna(subset=["return_pct"]).copy()
    d["abs_rate"] = d["return_pct"].abs()
    d = d.nlargest(20, "abs_rate").sort_values("return_pct")

    ys = d["store_name"].map(lambda x: _short(x, 25))
    colors = ["#f87171" if v < 0 else "#11CAA0" for v in d["return_pct"]]

    fig.add_trace(
        go.Bar(
            orientation="h",
            y=ys,
            x=d["return_pct"],
            marker=dict(color=colors, line=dict(width=0)),
            hovertemplate="<b>%{y}</b><br>Return Rate: %{x:.1f}%<extra></extra>",
            text=d["return_pct"].map(lambda x: f"{x:.1f}%"),
            textposition="outside",
            textfont=dict(size=10, color=MUTED),
        )
    )

    n = len(d)
    fig.update_layout(
        height=max(300, n * 32),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT, family=FONT, size=10),
        margin=dict(l=10, r=60, t=30, b=20),
        title=dict(
            text="Return Rate % — მაღაზიები",
            font=dict(size=13, color=TEXT),
            x=0.5,
            xanchor="center",
        ),
        xaxis=dict(
            gridcolor=GRID,
            zeroline=True,
            zerolinecolor="rgba(255,255,255,0.2)",
            ticksuffix="%",
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

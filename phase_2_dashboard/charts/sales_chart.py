"""Sales & Returns area/sparkline charts — mobile-first."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ui_theme import BORDER, FONT_BODY, MUTED, PRIMARY, PRIMARY_DIM, SUCCESS, SUCCESS_DIM, TEXT

BRAND_CYAN = PRIMARY
BRAND_MINT = SUCCESS
BRAND_CYAN_DIM = PRIMARY_DIM
BRAND_MINT_DIM = SUCCESS_DIM
FONT = FONT_BODY
GRID = BORDER


def sparkline(daily: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if daily is not None and not daily.empty:
        fig.add_trace(
            go.Scatter(
                x=daily["day"],
                y=daily["revenue_gel"],
                mode="lines",
                line=dict(color=BRAND_CYAN, width=2),
                fill="tozeroy",
                fillcolor=BRAND_CYAN_DIM,
                hovertemplate="%{x|%d %b}: <b>%{y:,.0f} ₾</b><extra></extra>",
            )
        )
    fig.update_layout(
        height=70,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        showlegend=False,
        dragmode=False,
    )
    return fig


def sales_returns_area(df: pd.DataFrame) -> go.Figure:
    """Mobile-friendly area chart."""
    fig = go.Figure()
    if df is None or df.empty:
        fig.add_annotation(
            text="მონაცემი არ არის",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(color=MUTED, size=13),
        )
        fig.update_layout(
            height=200,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
        )
        return fig

    d = df.sort_values("day").reset_index(drop=True)
    xs = pd.to_datetime(d["day"]).dt.normalize()
    y_ret = pd.to_numeric(d["returns_gel"], errors="coerce").fillna(0.0).clip(lower=0.0)

    fig.add_trace(
        go.Scatter(
            x=xs,
            y=d["sales_gel"],
            name="გაყიდვები",
            mode="lines",
            line=dict(color=BRAND_CYAN, width=2.5),
            fill="tozeroy",
            fillcolor=BRAND_CYAN_DIM,
            hovertemplate="%{x|%d %b}<br>გაყიდვები: <b>%{y:,.0f} ₾</b><extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=y_ret,
            name="დაბრუნება",
            mode="lines",
            line=dict(color=BRAND_MINT, width=2),
            fill="tozeroy",
            fillcolor=BRAND_MINT_DIM,
            hovertemplate="%{x|%d %b}<br>დაბრუნება: <b>%{y:,.0f} ₾</b><extra></extra>",
        )
    )
    fig.update_layout(
        height=260,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT, family=FONT, size=11),
        margin=dict(l=40, r=10, t=10, b=80),
        legend=dict(
            orientation="h",
            x=0.5,
            xanchor="center",
            y=-0.25,
            yanchor="top",
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11),
        ),
        xaxis=dict(
            gridcolor=GRID,
            zeroline=False,
            tickformat="%d %b",
            tickangle=-30,
            tickfont=dict(size=10, color=MUTED),
        ),
        yaxis=dict(
            gridcolor=GRID,
            zeroline=True,
            zerolinecolor="rgba(255,255,255,0.07)",
            tickformat=",.0f",
            rangemode="tozero",
            tickfont=dict(size=10, color=MUTED),
            ticksuffix=" ₾",
        ),
        dragmode=False,
        hovermode="x unified",
    )
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig

"""Stat card — reusable KPI block."""

from __future__ import annotations

import html

import streamlit as st


def _card_html(
    title: str,
    value: str,
    change: str | None = None,
    status: str = "neutral",
) -> str:
    status = (status or "neutral").lower()
    change_cls = {
        "success": "stat-change--success",
        "danger": "stat-change--danger",
        "warning": "stat-change--warning",
    }.get(status, "stat-change--muted")
    highlight = " stat-card--highlight" if status == "highlight" else ""
    change_html = ""
    if change:
        change_html = (
            f'<div class="stat-change {change_cls}">{html.escape(change)}</div>'
        )
    # Single-line HTML — indented multiline strings render as raw code in st.markdown.
    return (
        f'<div class="stat-card{highlight}">'
        f'<div class="stat-label">{html.escape(title)}</div>'
        f'<div class="stat-value">{html.escape(value)}</div>'
        f"{change_html}</div>"
    )


def render_stat_card(
    title: str,
    value: str,
    change: str | None = None,
    status: str = "neutral",
) -> None:
    """
    Render one KPI card.

    status: ``success`` | ``danger`` | ``warning`` | ``highlight`` | ``neutral``
    """
    st.markdown(_card_html(title, value, change, status), unsafe_allow_html=True)


def render_stat_grid(cards: list[dict]) -> None:
    """Render KPI row: each dict has title, value, optional change, status."""
    inner = "".join(
        _card_html(
            c["title"],
            c["value"],
            c.get("change"),
            c.get("status", "neutral"),
        )
        for c in cards
    )
    st.markdown(f'<div class="stat-grid">{inner}</div>', unsafe_allow_html=True)


def render_kpi_overview_row(
    main: dict,
    secondary: list[dict],
) -> None:
    """Prototype layout: 1 wide card + 3 cards, one HTML block (no st.columns)."""
    sec_html = "".join(
        _card_html(
            c["title"],
            c["value"],
            c.get("change"),
            c.get("status", "neutral"),
        )
        for c in secondary
    )
    main_html = _card_html(
        main["title"],
        main["value"],
        main.get("change"),
        main.get("status", "neutral"),
    )
    block = (
        '<div class="kpi-overview-row">'
        f'<div class="kpi-overview-main">{main_html}</div>'
        f'<div class="kpi-overview-secondary">{sec_html}</div>'
        "</div>"
    )
    st.markdown(block, unsafe_allow_html=True)

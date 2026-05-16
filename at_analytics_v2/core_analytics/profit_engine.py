"""
პუნქტი 5: მარჟა და ფასწარმოება — ლოგიკის სლოტი (შემდეგ ფაზაში).
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st


def margin_summary_placeholder(
    invoices: pd.DataFrame,
    lines: pd.DataFrame,
    start: date,
    end: date,
) -> dict:
    """დროებითი სტრუქტურა სანამ cost/margin მოდელი დაემატება."""
    return {
        "period": f"{start} → {end}",
        "invoices": len(invoices) if invoices is not None else 0,
        "line_rows": len(lines) if lines is not None else 0,
        "status": "placeholder",
    }


def render_tab(
    invoices: pd.DataFrame,
    lines: pd.DataFrame,
    d_start: date,
    d_end: date,
) -> None:
    st.subheader("მარჟა და ფასდებულება")
    info = margin_summary_placeholder(invoices, lines, d_start, d_end)
    st.json(info)
    st.caption(
        "აქ ჩაირთება ხარჯის ინტეგრაცია, ბრუტო მარჟა, რეკომენდებული ფასები და სენსიტივობის ანალიზი."
    )

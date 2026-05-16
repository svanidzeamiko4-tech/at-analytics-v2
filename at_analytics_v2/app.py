"""
AT Analytics v2 — თხელი შესასვლელი. ლოგიკა: ``core_analytics/*``.

გაშვება პროექტის ფესვიდან:
  streamlit run at_analytics_v2/app.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import streamlit as st

# პაკეტი ``core_analytics`` იმპორტისთვის
_APP_DIR = Path(__file__).resolve().parent
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from core_analytics import ai_assistant, overview_metrics, profit_engine, store_efficiency  # noqa: E402
from core_analytics.data_bridge import filter_invoices_by_period, load_dashboard_frames  # noqa: E402


def _default_dates(today: date) -> tuple[date, date]:
    from datetime import timedelta

    end = today
    start = end - timedelta(days=29)
    return start, end


def main() -> None:
    st.set_page_config(page_title="AT Analytics v2", layout="wide")
    st.title("AT Analytics v2")

    (inv, lines), db_path = load_dashboard_frames()
    today = date.today()
    d_start, d_end = _default_dates(today)

    with st.sidebar:
        st.caption(f"DB: `{db_path.name}`")
        d_start = st.date_input("დაწყება", value=d_start, key="v2_start")
        d_end = st.date_input("დასასრული", value=d_end, key="v2_end")
        if d_start > d_end:
            st.error("დაწყება > დასასრული")
            st.stop()
        inv_f = filter_invoices_by_period(inv, d_start, d_end)
        ai_assistant.render_sidebar(
            {"date_start": d_start, "date_end": d_end, "n_invoices": len(inv_f)}
        )

    overview_metrics.render_header_metrics(inv, lines, d_start, d_end)

    tab_eff, tab_profit = st.tabs(["მაღაზია / დაბრუნებები", "მარჟა / ფასები"])
    with tab_eff:
        store_efficiency.render_tab(inv, lines, d_start, d_end)
    with tab_profit:
        profit_engine.render_tab(inv, lines, d_start, d_end)


if __name__ == "__main__":
    main()

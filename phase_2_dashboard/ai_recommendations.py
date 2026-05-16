"""
Reserved for Phase 2+ AI-assisted insights (replenishment, anomalies, etc.).

``app.py`` imports this module so recommendations can be added without
restructuring the dashboard layout.
"""

from __future__ import annotations

from typing import Any

import html

import streamlit as st

# Same copy as former ``st.info`` sidebar slot; shown in main column on Phase 2 dashboard.
_AI_MAIN_BANNER_GEO = (
    "AI მოდელი ამუშავებს მონაცემებს მარაგების ოპტიმიზაციისთვის..."
)


def render_ai_main_strip() -> None:
    """Main-column AI label + banner (below brand header, above სწრაფი მიმოხილვა)."""
    text = html.escape(_AI_MAIN_BANNER_GEO)
    st.markdown(
        f"""
        <div class="ai-main-stack">
          <div class="ai-main-cap">AI / რეკომენდაციები</div>
          <div class="ai-main-banner">{text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_ai_sidebar_placeholder(_ctx: dict[str, Any] | None = None) -> None:
    """Extension slot for future model-backed suggestions."""
    st.markdown("---")
    st.caption("AI / რეკომენდაციები")
    st.info("AI მოდელი ამუშავებს მონაცემებს მარაგების ოპტიმიზაციისთვის...")

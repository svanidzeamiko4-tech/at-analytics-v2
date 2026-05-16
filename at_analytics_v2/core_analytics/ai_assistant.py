"""
პუნქტი 4: AI კონსულტანტი — Streamlit UI სლოტი (ფეიზი 2-ის placeholder-ზე დაყრდნობით).
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from .data_bridge import ensure_phase2_import_path


def render_sidebar(ctx: dict[str, Any] | None = None) -> None:
    ensure_phase2_import_path()
    import ai_recommendations  # noqa: E402

    ai_recommendations.render_ai_sidebar_placeholder(ctx)

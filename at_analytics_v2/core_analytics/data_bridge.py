"""Load read-only dashboard frames from existing ``phase_2_dashboard`` SQLite helpers."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

_PHASE2 = Path(__file__).resolve().parents[2] / "phase_2_dashboard"


def ensure_phase2_import_path() -> None:
    if str(_PHASE2) not in sys.path:
        sys.path.insert(0, str(_PHASE2))


def filter_invoices_by_period(invoices: Any, d_start: date, d_end: date) -> Any:
    """ინვოისები ``effective_date``-ით არჩეულ დღეებში (``phase_2_dashboard``)."""
    ensure_phase2_import_path()
    import data_loader as dl  # noqa: E402

    return dl.filter_by_date_range(invoices, "effective_date", d_start, d_end)


def load_dashboard_frames():
    ensure_phase2_import_path()
    import data_loader as dl  # noqa: E402

    db = dl.resolve_db_path()
    return dl.load_dashboard_frames(db), db

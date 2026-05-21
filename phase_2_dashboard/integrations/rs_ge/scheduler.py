"""
DEPRECATED — use APScheduler worker instead (Phase 2).

    python -m workers.rs_ge_worker

This module (``schedule`` lib, daily 02:00) is kept for reference only.
Production sync must run in a **separate process**, not Streamlit.
See ``docs/PHASE_2_RS_GE_WORKER.md``.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    import schedule
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: pip install schedule"
    ) from exc

from integrations.rs_ge import config
from integrations.rs_ge.sync import run_sync

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [rs_ge.scheduler] %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


def _job() -> None:
    try:
        df = run_sync()
        n = df["invoice_id"].nunique() if not df.empty else 0
        log.info("Sync OK: %s row(s), %s invoice(s)", len(df), n)
    except Exception:
        log.exception("Sync failed")


def run_forever() -> None:
    at = f"{int(config.SYNC_HOUR):02d}:00"
    schedule.every().day.at(at).do(_job)
    log.info("Scheduler started — daily at %s (USE_MOCK=%s)", at, config.USE_MOCK)
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    run_forever()

"""
RS.GE background worker — APScheduler, separate OS process.

Run from ``phase_2_dashboard/`` (never from Streamlit):

    python -m workers.rs_ge_worker
    python -m workers.rs_ge_worker --once

Requires: pip install apscheduler
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from loguru import logger

from core.config import get_settings
from core.logging_setup import configure_logging
from services.rs_sync import run_rs_ge_sync


def _configure_logger() -> None:
    settings = get_settings()
    log_path = settings.log_dir / "rs_ge_worker.log"
    configure_logging()
    logger.add(
        log_path,
        rotation="10 MB",
        retention="14 days",
        encoding="utf-8",
        level=settings.log_level,
    )


def _run_job() -> None:
    settings = get_settings()
    if not settings.use_postgres:
        logger.error(
            "USE_POSTGRES=false — worker idle. Set USE_POSTGRES=true in .env for Phase 2."
        )
        return
    try:
        result = run_rs_ge_sync()
        logger.info(
            "RS.GE sync OK: rows={} waybills={}",
            result.rows_written,
            result.waybills_count,
        )
    except Exception:
        logger.exception("RS.GE sync failed")


def run_scheduler() -> None:
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.interval import IntervalTrigger
    except ImportError as exc:
        raise SystemExit("Install APScheduler: pip install apscheduler") from exc

    settings = get_settings()
    minutes = max(1, int(settings.rs_sync_interval_minutes))

    scheduler = BlockingScheduler()
    scheduler.add_job(
        _run_job,
        trigger=IntervalTrigger(minutes=minutes),
        id="rs_ge_sync",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )

    logger.info(
        "RS.GE worker started — every {} min, USE_MOCK={}, USE_POSTGRES={}",
        minutes,
        settings.rs_ge_use_mock,
        settings.use_postgres,
    )
    _run_job()
    scheduler.start()


def main() -> None:
    parser = argparse.ArgumentParser(description="RS.GE APScheduler worker")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single sync cycle and exit",
    )
    args = parser.parse_args()

    _configure_logger()

    if args.once:
        _run_job()
        return

    run_scheduler()


if __name__ == "__main__":
    main()

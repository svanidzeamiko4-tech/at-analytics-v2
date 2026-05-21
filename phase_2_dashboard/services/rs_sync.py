"""
RS.GE sync orchestration (Phase 2).

Uses existing ``sync.fetch_xml`` and ``parser.parse_invoices`` without modifying them.
Writes to PostgreSQL when ``USE_POSTGRES=true``; optional SQLite fallback for local dev.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass

import pandas as pd

from core.config import get_settings
from integrations.rs_ge.parser import parse_invoices
from integrations.rs_ge.sync import fetch_xml, save_to_db


@dataclass(frozen=True)
class RsSyncResult:
    status: str
    rows_written: int
    waybills_count: int
    error_message: str | None = None


def _bridge_rs_ge_config() -> None:
    """Map ``core.config`` env vars onto legacy ``integrations.rs_ge.config`` module."""
    from integrations.rs_ge import config as rs_cfg

    s = get_settings()
    rs_cfg.USE_MOCK = s.rs_ge_use_mock
    rs_cfg.RS_GE_USERNAME = s.rs_ge_username
    rs_cfg.RS_GE_PASSWORD = s.rs_ge_password
    if s.rs_ge_soap_url:
        rs_cfg.SOAP_URL = s.rs_ge_soap_url


def _count_waybills(df: pd.DataFrame) -> int:
    if df.empty or "invoice_id" not in df.columns:
        return 0
    return int(df["invoice_id"].nunique())


def run_rs_ge_sync(*, use_sqlite_fallback: bool = False) -> RsSyncResult:
    """
    One sync cycle: fetch → parse → persist → audit row in ``sync_runs``.

    Raises on failure after recording ``failed`` in ``sync_runs`` when Postgres is enabled.
    """
    settings = get_settings()
    _bridge_rs_ge_config()

    run = None
    repo = None
    if settings.use_postgres:
        import services.rs_waybill_repository as repo

        run = repo.start_sync_run()

    try:
        xml_text = fetch_xml()
        ET.fromstring(xml_text.encode("utf-8"))
        df = parse_invoices(xml_text)
        waybills_count = _count_waybills(df)

        if settings.use_postgres and repo is not None and run is not None:
            rows_written = repo.upsert_waybills(df)
            repo.finish_sync_run(
                run,
                status="success",
                rows_written=rows_written,
                waybills_count=waybills_count,
            )
            return RsSyncResult("success", rows_written, waybills_count)

        if use_sqlite_fallback:
            rows_written = save_to_db(df)
            return RsSyncResult("success", rows_written, waybills_count)

        raise RuntimeError(
            "USE_POSTGRES=false — worker sync skipped. "
            "Set USE_POSTGRES=true or pass use_sqlite_fallback=True for dev."
        )

    except Exception as exc:
        if settings.use_postgres and repo is not None and run is not None:
            repo.finish_sync_run(
                run,
                status="failed",
                rows_written=0,
                waybills_count=0,
                error_message=str(exc),
            )
        raise


def main() -> None:
    """CLI: single sync cycle (testing)."""
    settings = get_settings()
    result = run_rs_ge_sync(use_sqlite_fallback=not settings.use_postgres)
    print(
        f"status={result.status} rows={result.rows_written} "
        f"waybills={result.waybills_count}"
    )


if __name__ == "__main__":
    main()

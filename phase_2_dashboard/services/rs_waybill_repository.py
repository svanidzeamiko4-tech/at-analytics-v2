"""
PostgreSQL persistence for RS.GE waybills and sync audit (Phase 2).

Used only by the background worker — not by Streamlit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy.dialects.postgresql import insert

from database.models.integrations import SyncRun, Waybill
from database.session import get_session


@dataclass(frozen=True)
class SyncRunRecord:
    id: int
    started_at: datetime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def start_sync_run() -> SyncRunRecord:
    started = _utcnow()
    with get_session() as session:
        row = SyncRun(started_at=started, status="running")
        session.add(row)
        session.flush()
        return SyncRunRecord(id=int(row.id), started_at=started)


def finish_sync_run(
    run: SyncRunRecord,
    *,
    status: str,
    rows_written: int = 0,
    waybills_count: int = 0,
    error_message: str | None = None,
) -> None:
    with get_session() as session:
        row = session.get(SyncRun, run.id)
        if row is None:
            return
        row.finished_at = _utcnow()
        row.status = status
        row.rows_written = rows_written
        row.waybills_count = waybills_count
        row.error_message = (error_message or "")[:4000] or None


def upsert_waybills(df: pd.DataFrame) -> int:
    """Upsert parsed lines into ``integrations.waybills``. Returns rows touched."""
    if df.empty:
        return 0

    synced_at = _utcnow()
    payload = []
    for r in df.itertuples(index=False):
        payload.append(
            {
                "invoice_id": str(r.invoice_id),
                "date": str(r.date) if r.date is not None else None,
                "seller_name": str(r.seller_name) if r.seller_name else None,
                "seller_address": str(r.seller_address) if r.seller_address else None,
                "buyer_name": str(r.buyer_name) if r.buyer_name else None,
                "buyer_address": str(r.buyer_address) if r.buyer_address else None,
                "buyer_barcode": str(r.buyer_barcode) if r.buyer_barcode else None,
                "product_name": str(r.product_name) if r.product_name else None,
                "quantity": float(r.quantity),
                "price": float(r.price),
                "line_total": float(r.line_total),
                "synced_at": synced_at,
            }
        )

    stmt = insert(Waybill).values(payload)
    excluded = stmt.excluded
    stmt = stmt.on_conflict_do_update(
        constraint="uq_waybills_line",
        set_={
            "date": excluded.date,
            "seller_name": excluded.seller_name,
            "seller_address": excluded.seller_address,
            "buyer_name": excluded.buyer_name,
            "buyer_address": excluded.buyer_address,
            "quantity": excluded.quantity,
            "price": excluded.price,
            "line_total": excluded.line_total,
            "synced_at": excluded.synced_at,
        },
    )

    with get_session() as session:
        session.execute(stmt)
    return len(payload)

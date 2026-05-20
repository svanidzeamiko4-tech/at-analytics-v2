"""Sync RS.ge waybills into ``amiko_v3.db`` (table ``waybills``)."""

from __future__ import annotations

import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd

from integrations.rs_ge import config
from integrations.rs_ge.parser import parse_invoices

_MOCK_PATH = Path(__file__).resolve().parent / "mock_data.xml"
_DB_PATH = Path(__file__).resolve().parents[3] / "amiko_v3.db"

_WAYBILLS_DDL = """
CREATE TABLE IF NOT EXISTS waybills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id TEXT NOT NULL,
    date TEXT,
    seller_name TEXT,
    seller_address TEXT,
    buyer_name TEXT,
    buyer_address TEXT,
    buyer_barcode TEXT,
    product_name TEXT,
    quantity REAL,
    price REAL,
    line_total REAL,
    synced_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (invoice_id, product_name, buyer_barcode)
);
CREATE INDEX IF NOT EXISTS idx_waybills_invoice ON waybills(invoice_id);
CREATE INDEX IF NOT EXISTS idx_waybills_buyer ON waybills(buyer_name);
"""


def get_db_path() -> Path:
    return _DB_PATH


def _load_mock_xml() -> str:
    if not _MOCK_PATH.is_file():
        raise FileNotFoundError(f"Mock XML not found: {_MOCK_PATH}")
    return _MOCK_PATH.read_text(encoding="utf-8")


def _fetch_soap_xml(username: str, password: str, url: str) -> str:
    """POST SOAP request to RS.ge NTO service (response shape may vary)."""
    import urllib.error
    import urllib.request

    body = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://tempuri.org/">
  <soap:Body>
    <tns:GetWaybills>
      <tns:Username>{escape(username)}</tns:Username>
      <tns:Password>{escape(password)}</tns:Password>
    </tns:GetWaybills>
  </soap:Body>
</soap:Envelope>"""
    req = urllib.request.Request(
        url,
        data=body.encode("utf-8"),
        headers={
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": "http://tempuri.org/GetWaybills",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"SOAP HTTP {exc.code}: {detail}") from exc


def fetch_xml() -> str:
    if config.USE_MOCK:
        return _load_mock_xml()
    if not config.RS_GE_USERNAME or not config.RS_GE_PASSWORD:
        raise ValueError("RS_GE_USERNAME and RS_GE_PASSWORD required when USE_MOCK=False")
    return _fetch_soap_xml(config.RS_GE_USERNAME, config.RS_GE_PASSWORD, config.SOAP_URL)


def save_to_db(df: pd.DataFrame, db_path: Path | None = None) -> int:
    """Upsert parsed rows into ``waybills`` table. Returns rows written."""
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    synced_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(path)
    try:
        conn.executescript(_WAYBILLS_DDL)
        if df.empty:
            conn.commit()
            return 0

        sql = """
            INSERT INTO waybills (
                invoice_id, date, seller_name, seller_address,
                buyer_name, buyer_address, buyer_barcode,
                product_name, quantity, price, line_total, synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(invoice_id, product_name, buyer_barcode) DO UPDATE SET
                date=excluded.date,
                seller_name=excluded.seller_name,
                seller_address=excluded.seller_address,
                buyer_name=excluded.buyer_name,
                buyer_address=excluded.buyer_address,
                quantity=excluded.quantity,
                price=excluded.price,
                line_total=excluded.line_total,
                synced_at=excluded.synced_at
        """
        rows = [
            (
                str(r.invoice_id),
                str(r.date),
                str(r.seller_name),
                str(r.seller_address),
                str(r.buyer_name),
                str(r.buyer_address),
                str(r.buyer_barcode),
                str(r.product_name),
                float(r.quantity),
                float(r.price),
                float(r.line_total),
                synced_at,
            )
            for r in df.itertuples(index=False)
        ]
        conn.executemany(sql, rows)
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def run_sync(db_path: Path | None = None) -> pd.DataFrame:
    """Fetch XML (mock or SOAP), parse, persist to SQLite. Returns parsed DataFrame."""
    xml_text = fetch_xml()
    # Validate XML early
    ET.fromstring(xml_text.encode("utf-8"))
    df = parse_invoices(xml_text)
    save_to_db(df, db_path)
    return df


if __name__ == "__main__":
    frame = run_sync()
    print(
        f"Synced {len(frame)} line(s), "
        f"{frame['invoice_id'].nunique() if not frame.empty else 0} invoice(s) -> {get_db_path()}"
    )

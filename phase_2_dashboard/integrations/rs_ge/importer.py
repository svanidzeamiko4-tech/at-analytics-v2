"""
RS.ge waybill XML → amiko_v3.db (invoices + invoice_items + stores).
გამოიძახება sync.py-დან run_sync()-ის შემდეგ.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from integrations.rs_ge.parser import parse_invoices

_DB_PATH = Path(__file__).resolve().parents[3] / "amiko_v3.db"


def get_or_create_store(conn: sqlite3.Connection, buyer_name: str, buyer_address: str) -> int:
    """stores ცხრილში მოძებნე ან შექმენი მაღაზია. დააბრუნე store_id."""
    cur = conn.execute(
        "SELECT id FROM stores WHERE name = ? LIMIT 1", (buyer_name,)
    )
    row = cur.fetchone()
    if row:
        return int(row[0])
    cur = conn.execute(
        "INSERT INTO stores (name, address) VALUES (?, ?)",
        (buyer_name, buyer_address),
    )
    conn.commit()
    return int(cur.lastrowid)


def import_waybills_to_db(xml_text: str, db_path: Path | None = None) -> dict:
    """
    XML → parse → invoices + invoice_items + stores.
    დააბრუნებს: {'invoices': N, 'items': N, 'stores_created': N}
    """
    path = db_path or _DB_PATH
    df = parse_invoices(xml_text)
    if df.empty:
        return {"invoices": 0, "items": 0, "stores_created": 0}

    conn = sqlite3.connect(path)
    invoices_written = 0
    items_written = 0
    stores_created = 0
    try:
        for invoice_id, group in df.groupby("invoice_id"):
            first = group.iloc[0]
            buyer_name = str(first.get("buyer_name", ""))
            buyer_address = str(first.get("buyer_address", ""))
            date_raw = str(first.get("date", ""))

            cur = conn.execute(
                "SELECT id FROM stores WHERE name = ? LIMIT 1", (buyer_name,)
            )
            row = cur.fetchone()
            if row:
                store_id = int(row[0])
            else:
                cur = conn.execute(
                    "INSERT INTO stores (name, address) VALUES (?, ?)",
                    (buyer_name, buyer_address),
                )
                store_id = int(cur.lastrowid)
                stores_created += 1

            total = (
                float(group["line_total"].sum())
                if "line_total" in group.columns
                else 0.0
            )
            cur2 = conn.execute(
                "SELECT id FROM invoices WHERE invoice_number = ? LIMIT 1",
                (str(invoice_id),),
            )
            existing = cur2.fetchone()
            if existing:
                inv_db_id = int(existing[0])
            else:
                cur2 = conn.execute(
                    """INSERT INTO invoices
                    (store_id, invoice_number, invoice_date, total, subtotal, source_file)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        store_id,
                        str(invoice_id),
                        date_raw,
                        total,
                        total,
                        "rs_ge_sync",
                    ),
                )
                inv_db_id = int(cur2.lastrowid)
                invoices_written += 1

            for _, item in group.iterrows():
                product_name = str(item.get("product_name", ""))
                quantity = float(item.get("quantity", 0))
                price = float(item.get("price", 0))
                line_total = float(item.get("line_total", quantity * price))
                conn.execute(
                    """INSERT OR IGNORE INTO invoice_items
                    (invoice_id, description, quantity, unit_price, line_total)
                    VALUES (?, ?, ?, ?, ?)""",
                    (inv_db_id, product_name, quantity, price, line_total),
                )
                items_written += 1
        conn.commit()
    finally:
        conn.close()

    return {
        "invoices": invoices_written,
        "items": items_written,
        "stores_created": stores_created,
    }

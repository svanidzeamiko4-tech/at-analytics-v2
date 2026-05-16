"""
Initialize SQLite database amiko_v3.db for Amiko Analytics V3.

Creates tables: stores, products, invoices, invoice_items, product_merge_rules.
Text is stored as UTF-8 (SQLite default); Georgian is supported in TEXT columns.
Run: python database_init.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_NAME = "amiko_v3.db"


def get_db_path() -> Path:
    return Path(__file__).resolve().parent / DB_NAME


def init_database(db_path: Path | None = None) -> Path:
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    try:
        # UTF-8 storage for all TEXT (must be set before any schema on a new DB)
        cur = conn.cursor()
        cur.execute("PRAGMA encoding = 'UTF-8'")
        cur.execute("PRAGMA foreign_keys = ON")

        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS stores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE,
                name TEXT NOT NULL,
                address TEXT,
                city TEXT,
                phone TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT UNIQUE,
                name TEXT NOT NULL,
                category TEXT,
                unit TEXT,
                default_unit_price REAL,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT NOT NULL,
                store_id INTEGER NOT NULL,
                invoice_date TEXT,
                subtotal REAL,
                tax_total REAL,
                total REAL,
                currency TEXT NOT NULL DEFAULT 'GEL',
                source_file TEXT,
                raw_text TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE (store_id, invoice_number),
                FOREIGN KEY (store_id) REFERENCES stores(id)
            );

            CREATE TABLE IF NOT EXISTS invoice_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                product_id INTEGER,
                line_no INTEGER,
                description TEXT,
                quantity REAL NOT NULL DEFAULT 1,
                unit_price REAL,
                discount REAL DEFAULT 0,
                line_total REAL,
                vat_rate REAL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id)
            );

            CREATE INDEX IF NOT EXISTS idx_invoices_store
                ON invoices(store_id);
            CREATE INDEX IF NOT EXISTS idx_invoices_date
                ON invoices(invoice_date);
            CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice
                ON invoice_items(invoice_id);
            CREATE INDEX IF NOT EXISTS idx_invoice_items_product
                ON invoice_items(product_id);

            CREATE TABLE IF NOT EXISTS product_merge_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                priority INTEGER NOT NULL DEFAULT 0,
                canonical_name TEXT NOT NULL,
                m1 TEXT NOT NULL,
                m2 TEXT,
                m3 TEXT,
                notes TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_product_merge_priority
                ON product_merge_rules(priority DESC);
            """
        )
        conn.commit()
    finally:
        conn.close()

    return path


if __name__ == "__main__":
    out = init_database()
    print(f"Database ready: {out}")

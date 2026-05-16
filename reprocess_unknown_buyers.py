"""
Delete invoices tied to the placeholder store ``(უცნობი მყიდველი)`` and re-run
``main_processor.process_pdf_file`` for each source PDF so updated OCR rules apply.

Usage (from project folder):
  python reprocess_unknown_buyers.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from database_init import get_db_path
from main_processor import FUZZY_THRESHOLD, _ensure_processed_dir, process_pdf_file


UNKNOWN = "(უცნობი მყიდველი)"


def _resolve_pdf_path(root: Path, name: str) -> Path | None:
    """Resolve ``invoice_104.pdf`` after ``main_processor`` renamed it to ``invoice_104_1.pdf``."""
    for base in (root, root / "processed"):
        p = base / name
        if p.is_file():
            return p
    stem = Path(name).stem
    for base in (root, root / "processed"):
        matches = sorted(base.glob(f"{stem}_*.pdf"))
        if matches:
            return matches[0]
    return None


def main() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    root = Path(__file__).resolve().parent
    db_path = get_db_path()
    if not db_path.is_file():
        raise SystemExit(f"No database: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DISTINCT i.source_file
        FROM invoices i
        JOIN stores s ON s.id = i.store_id
        WHERE s.name = ?
        ORDER BY i.source_file
        """,
        (UNKNOWN,),
    )
    files = [row[0] for row in cur.fetchall() if row[0]]
    if not files:
        print("No invoices with unknown buyer store — nothing to do.")
        conn.close()
        return

    cur.execute(
        """
        SELECT i.id FROM invoices i
        JOIN stores s ON s.id = i.store_id
        WHERE s.name = ?
        """,
        (UNKNOWN,),
    )
    inv_ids = [int(r[0]) for r in cur.fetchall()]
    for iid in inv_ids:
        cur.execute("DELETE FROM invoice_items WHERE invoice_id = ?", (iid,))
    cur.execute(
        """
        DELETE FROM invoices WHERE id IN (
            SELECT i.id FROM invoices i
            JOIN stores s ON s.id = i.store_id
            WHERE s.name = ?
        )
        """,
        (UNKNOWN,),
    )
    cur.execute("DELETE FROM stores WHERE name = ?", (UNKNOWN,))
    conn.commit()
    conn.close()
    print(f"Removed {len(inv_ids)} invoice(s) and placeholder store rows for {UNKNOWN!r}")

    processed_dir = _ensure_processed_dir(root)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        for i, name in enumerate(files, start=1):
            pdf = _resolve_pdf_path(root, name)
            if pdf is None:
                print(f"[{i}/{len(files)}] MISSING {name!r} (not in project root or processed/)")
                continue
            ok = process_pdf_file(conn, pdf, i, len(files), processed_dir, FUZZY_THRESHOLD)
            print(f"    → {'OK' if ok else 'FAILED'}", flush=True)
    finally:
        conn.close()
    print("Done.")


if __name__ == "__main__":
    main()

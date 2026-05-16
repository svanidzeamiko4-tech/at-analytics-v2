"""
Reset stores.address where it contains supplier HQ fragments,
then re-scan processed PDFs to populate correct branch addresses.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from database_init import get_db_path
from ocr_engine import process_pdf

# These are supplier HQ addresses — NOT store addresses
BAD_ADDRESSES = (
    "თ.ერისთავის",
    "ერისთავის 1",
    "ერისთავის_1",
)


def _is_bad_address(addr: str) -> bool:
    return any(frag in (addr or "") for frag in BAD_ADDRESSES)


def main() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    root = Path(__file__).resolve().parent
    db_path = get_db_path()
    processed = root / "processed"

    # Step 1: Reset bad addresses in DB
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()
    cur.execute("SELECT id, name, address FROM stores")
    rows = cur.fetchall()
    reset_count = 0
    for sid, name, addr in rows:
        if addr and _is_bad_address(str(addr)):
            conn.execute("UPDATE stores SET address = NULL WHERE id = ?", (sid,))
            reset_count += 1
            print(f"  Reset store_id={sid} ({name}): '{addr}' → NULL")
    conn.commit()
    print(f"\nReset {reset_count} bad address(es). Now re-scanning PDFs...\n")

    # Step 2: Re-scan PDFs and update with correct branch address
    pdfs = sorted(processed.glob("*.pdf"))
    print(f"Found {len(pdfs)} PDFs")

    updated = 0

    for pdf in pdfs:
        try:
            result = process_pdf(pdf, stores_db_path=db_path)
        except Exception as e:
            print(f"  ERROR {pdf.name}: {e}")
            continue

        if not result.matched_store_id:
            continue
        if not result.store_branch_address:
            continue
        if _is_bad_address(result.store_branch_address):
            continue

        cur = conn.cursor()
        cur.execute(
            "SELECT COALESCE(address, '') FROM stores WHERE id = ?",
            (result.matched_store_id,),
        )
        row = cur.fetchone()
        current = (row[0] or "").strip() if row else ""

        if not current:
            conn.execute(
                "UPDATE stores SET address = ? WHERE id = ?",
                (
                    result.store_branch_address.strip(),
                    result.matched_store_id,
                ),
            )
            conn.commit()
            updated += 1
            print(
                f"  Updated id={result.matched_store_id} → {result.store_branch_address}"
            )

    conn.close()
    print(f"\nDone. Updated {updated} store address(es).")

    # Step 3: Show final result
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, name, address FROM stores ORDER BY name")
    print("\n=== Final store addresses ===")
    for sid, name, addr in cur.fetchall():
        status = "✓" if addr and not _is_bad_address(str(addr)) else "✗ STILL BAD"
        print(f"  {sid:4d}  {status}  {(addr or '(empty)')[:55]:55s}  {name}")
    conn.close()


if __name__ == "__main__":
    main()

"""
Amiko Analytics V3 — Stage 4: bulk PDF → SQLite (amiko_v3.db).

Scans the script directory for *.pdf, runs ocr_engine.process_pdf on each,
writes stores / products / invoices / invoice_items, then moves PDFs to ./processed/.

Run from project folder:
  python main_processor.py
  python main_processor.py 3.pdf 5.pdf
  python main_processor.py processed\\backup\\3.pdf
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
import sys
from pathlib import Path

from database_init import get_db_path, init_database
from ocr_engine import PdfProcessResult, process_pdf


FUZZY_THRESHOLD = 0.9


def _parse_float(s: str | None) -> float | None:
    if s is None or not str(s).strip():
        return None
    try:
        return float(str(s).replace(",", ".").strip())
    except ValueError:
        return None


def _ensure_processed_dir(root: Path) -> Path:
    d = root / "processed"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _invoice_exists(cur: sqlite3.Cursor, store_id: int, invoice_number: str) -> bool:
    cur.execute(
        "SELECT 1 FROM invoices WHERE store_id = ? AND invoice_number = ? LIMIT 1",
        (store_id, invoice_number),
    )
    return cur.fetchone() is not None


def _resolve_store_id(
    cur: sqlite3.Cursor,
    result: PdfProcessResult,
    fuzzy_threshold: float,
) -> tuple[int, str]:
    """
    Resolve store by chain name + branch address when available; else fuzzy name match.

    Same legal name at different branch addresses get separate ``stores`` rows.
    Returns (store_id, action_label for logging).
    """
    _ = fuzzy_threshold  # threshold applied in process_pdf before matched_store_id is set

    branch_addr = (getattr(result, "store_branch_address", None) or "").strip()

    if branch_addr and result.matched_store_id is not None:
        cur.execute(
            "SELECT id FROM stores WHERE id = ? AND TRIM(COALESCE(address, '')) = ?",
            (result.matched_store_id, branch_addr),
        )
        row = cur.fetchone()
        if row:
            return int(row[0]), f"linked store id={row[0]} (exact chain+address)"

        cur.execute(
            "SELECT id FROM stores WHERE name = ? AND TRIM(COALESCE(address, '')) = ?",
            ((result.store_name or "").strip(), branch_addr),
        )
        row = cur.fetchone()
        if row:
            return int(row[0]), f"linked store id={row[0]} (chain+address match)"

        name = (result.store_name or "").strip() or "(უცნობი მყიდველი)"
        cur.execute(
            "INSERT INTO stores (name, address) VALUES (?, ?)",
            (name, branch_addr),
        )
        sid = int(cur.lastrowid)
        return sid, f"new branch store id={sid} ({name!r} @ {branch_addr!r})"

    if result.matched_store_id is not None:
        sid = result.matched_store_id
        if branch_addr:
            cur.execute("SELECT COALESCE(address, '') FROM stores WHERE id = ?", (sid,))
            row = cur.fetchone()
            if row is not None and not (row[0] or "").strip():
                cur.execute(
                    "UPDATE stores SET address = ? WHERE id = ?",
                    (branch_addr, sid),
                )
        return sid, f"linked store id={sid} (fuzzy {result.fuzzy_match_score:.2f})"

    name = (result.store_name or "").strip() or "(უცნობი მყიდველი)"
    addr = branch_addr or (result.buyer_address or "").strip() or None
    cur.execute(
        "INSERT INTO stores (name, address) VALUES (?, ?)",
        (name, addr),
    )
    sid = int(cur.lastrowid)
    return sid, f"new store id={sid} ({name!r})"


def _get_or_create_product_id(
    cur: sqlite3.Cursor,
    name: str,
    unit_price: float | None,
) -> int | None:
    name = name.strip()
    if not name:
        return None
    cur.execute("SELECT id FROM products WHERE name = ? LIMIT 1", (name,))
    row = cur.fetchone()
    if row:
        return int(row[0])
    cur.execute(
        """
        INSERT INTO products (name, unit, default_unit_price)
        VALUES (?, 'ცალი', ?)
        """,
        (name, unit_price),
    )
    return int(cur.lastrowid)


def _insert_invoice_and_items(
    cur: sqlite3.Cursor,
    store_id: int,
    result: PdfProcessResult,
    pdf_name: str,
) -> tuple[float | None, int]:
    """Insert invoice + line items. Returns (computed_total, items_inserted)."""
    inv_no = (result.waybill_number or "").strip() or Path(pdf_name).stem
    notes_parts = []
    if result.invoice_time:
        notes_parts.append(f"time={result.invoice_time}")
    if result.warnings:
        notes_parts.append("warnings: " + "; ".join(result.warnings[:5]))
    notes = " | ".join(notes_parts) if notes_parts else None

    line_totals: list[float] = []
    items_inserted = 0

    cur.execute(
        """
        INSERT INTO invoices (
            invoice_number, store_id, invoice_date, subtotal, tax_total, total,
            currency, source_file, raw_text, notes
        ) VALUES (?, ?, ?, NULL, NULL, NULL, 'GEL', ?, ?, ?)
        """,
        (
            inv_no,
            store_id,
            result.date,
            pdf_name,
            result.raw_text[:500000] if result.raw_text else None,
            notes,
        ),
    )
    invoice_id = int(cur.lastrowid)

    for i, row in enumerate(result.products, start=1):
        qty = _parse_float(row.quantity) or 0.0
        unit_p = _parse_float(row.price)
        line_total = None
        if unit_p is not None:
            line_total = round(qty * unit_p, 4)
            line_totals.append(line_total)

        pid = _get_or_create_product_id(cur, row.name, unit_p)

        cur.execute(
            """
            INSERT INTO invoice_items (
                invoice_id, product_id, line_no, description,
                quantity, unit_price, line_total
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                invoice_id,
                pid,
                i,
                row.name,
                qty,
                unit_p,
                line_total,
            ),
        )
        items_inserted += 1

    subtotal = round(sum(line_totals), 4) if line_totals else None
    cur.execute(
        "UPDATE invoices SET subtotal = ?, total = ? WHERE id = ?",
        (subtotal, subtotal, invoice_id),
    )
    return subtotal, items_inserted


def process_pdf_file(
    conn: sqlite3.Connection,
    pdf_path: Path,
    index: int,
    total: int,
    processed_dir: Path,
    fuzzy_threshold: float,
) -> bool:
    """Returns True if PDF was moved to processed/."""
    rel = pdf_path.name
    print(f"[{index}/{total}] {rel} …", flush=True)

    try:
        result = process_pdf(
            pdf_path,
            stores_db_path=get_db_path(),
            fuzzy_threshold=fuzzy_threshold,
        )
    except Exception as exc:
        print(f"    ERROR extract: {exc}", flush=True)
        return False

    inv_no = (result.waybill_number or "").strip() or pdf_path.stem
    cur = conn.cursor()

    try:
        store_id, store_action = _resolve_store_id(cur, result, fuzzy_threshold)
        print(f"    store: {store_action}", flush=True)

        if _invoice_exists(cur, store_id, inv_no):
            print(
                f"    skip DB: invoice already exists store_id={store_id} №{inv_no!r}",
                flush=True,
            )
        else:
            total_amt, n_items = _insert_invoice_and_items(
                cur, store_id, result, rel
            )
            print(
                f"    saved invoice №{inv_no!r}, items={n_items}, total={total_amt}",
                flush=True,
            )

        conn.commit()
    except Exception as exc:
        conn.rollback()
        print(f"    ERROR database: {exc}", flush=True)
        return False

    dest = processed_dir / rel
    if dest.exists():
        stem, suf = pdf_path.stem, pdf_path.suffix
        n = 1
        while True:
            dest = processed_dir / f"{stem}_{n}{suf}"
            if not dest.exists():
                break
            n += 1
    shutil.move(str(pdf_path), str(dest))
    print(f"    moved → {dest.relative_to(pdf_path.parent)}", flush=True)
    return True


def _collect_pdf_targets(root: Path, argv: list[str]) -> list[Path]:
    """All *.pdf in ``root``, or only the PDF paths given on the command line."""
    if len(argv) <= 1:
        return sorted(root.glob("*.pdf"))
    out: list[Path] = []
    for a in argv[1:]:
        p = Path(a).expanduser()
        if not p.is_absolute():
            p = (root / p).resolve()
        else:
            p = p.resolve()
        if p.suffix.lower() != ".pdf":
            print(f"Warning: not a .pdf, skipping: {p}", flush=True)
            continue
        if p.is_file():
            out.append(p)
        else:
            print(f"Warning: file not found, skipping: {p}", flush=True)
    return out


def main() -> None:
    root = Path(__file__).resolve().parent
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    if not logging.root.handlers:
        logging.basicConfig(
            level=logging.WARNING,
            format="%(levelname)s %(name)s: %(message)s",
        )

    db_path = get_db_path()
    if not db_path.is_file():
        print(f"Creating database {db_path.name} …")
        init_database(db_path)

    pdfs = _collect_pdf_targets(root, sys.argv)
    if not pdfs:
        print(f"No PDF files to process (check paths / {root}\\*.pdf )")
        return

    processed_dir = _ensure_processed_dir(root)
    print(f"Found {len(pdfs)} PDF(s). Database: {db_path}")
    print(f"Processed folder: {processed_dir}")
    print("-" * 60)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        for i, pdf_path in enumerate(pdfs, start=1):
            process_pdf_file(conn, pdf_path, i, len(pdfs), processed_dir, FUZZY_THRESHOLD)
    finally:
        conn.close()

    print("-" * 60)
    print("Done.")


if __name__ == "__main__":
    main()

"""
Link waybill appendices (დანართი) that were stored as ``(უცნობი მყიდველი)``
to the real buyer by matching the **waybill / ზედნადები №** (e.g. ``0968606515``).

Appendix PDFs often have ``invoice_number`` set to the PDF stem (``invoice_19_1``)
because ``waybill_number`` was empty at insert; the same numeric waybill is still
present in ``raw_text``. This script uses ``ocr_engine._extract_waybill`` on
``raw_text`` (and falls back to a non-stem ``invoice_number``) to find a sibling
invoice that already has a real ``store_id``.

Because ``invoices`` has ``UNIQUE (store_id, invoice_number)``, we cannot keep two
rows with the same store + number. When a parent invoice already exists for that
number, appendix line items are **merged** into the parent invoice and the
unknown appendix invoice row is removed.

After stitching, deletes orphan ``(უცნობი მყიდველი)`` rows from ``stores`` that
are no longer referenced by any invoice.

Usage (from project folder):
  python stitch_appendices.py
"""

from __future__ import annotations

import re
import sqlite3
import sys

from database_init import get_db_path
from ocr_engine import _extract_waybill

UNKNOWN = "(უცნობი მყიდველი)"
_STEM_INVOICE_RE = re.compile(r"^invoice_\d", re.IGNORECASE)


def _norm_waybill_token(s: str) -> str:
    return re.sub(r"\s+", "", (s or "").strip())


def _expand_waybill_match_keys(k: str) -> set[str]:
    """Same physical waybill may appear as ``0964437553`` or ``0964437553/5``."""
    s = _norm_waybill_token(k)
    if not s:
        return set()
    out: set[str] = {s}
    if "/" in s:
        base = s.split("/", 1)[0].strip()
        if len(base) >= 8:
            out.add(base)
    return out


def _waybill_keys_for_row(invoice_number: str, raw_text: str | None) -> set[str]:
    """Keys that might identify the same RS.ge waybill across main page vs დანართი."""
    keys: set[str] = set()
    w = _extract_waybill(raw_text or "")
    if w:
        keys.update(_expand_waybill_match_keys(w))
    inv = (invoice_number or "").strip()
    if inv and not _STEM_INVOICE_RE.match(inv):
        keys.update(_expand_waybill_match_keys(inv))
    return {k for k in keys if len(k) >= 6}


def _parent_index_by_waybill(cur: sqlite3.Cursor) -> dict[str, tuple[int, int]]:
    """First (invoice_id, store_id) per waybill key among non-unknown stores."""
    cur.execute(
        """
        SELECT i.id, i.invoice_number, i.raw_text, i.store_id
        FROM invoices i
        JOIN stores s ON s.id = i.store_id
        WHERE TRIM(s.name) != ?
        ORDER BY i.id ASC
        """,
        (UNKNOWN,),
    )
    out: dict[str, tuple[int, int]] = {}
    for inv_id, inv_no, raw, sid in cur.fetchall():
        for k in _waybill_keys_for_row(str(inv_no or ""), raw):
            if k not in out:
                out[k] = (int(inv_id), int(sid))
    return out


def _recompute_invoice_totals(cur: sqlite3.Cursor, invoice_id: int) -> None:
    cur.execute(
        "SELECT SUM(line_total) FROM invoice_items WHERE invoice_id = ?",
        (invoice_id,),
    )
    row = cur.fetchone()
    t = row[0] if row else None
    if t is None:
        cur.execute(
            "UPDATE invoices SET subtotal = NULL, total = NULL WHERE id = ?",
            (invoice_id,),
        )
    else:
        sub = round(float(t), 4)
        cur.execute(
            "UPDATE invoices SET subtotal = ?, total = ? WHERE id = ?",
            (sub, sub, invoice_id),
        )


def _find_parent_invoice(
    cur: sqlite3.Cursor, invoice_number: str
) -> tuple[int, int] | None:
    """Return ``(invoice_id, store_id)`` of the earliest non-unknown invoice with this number."""
    cur.execute(
        """
        SELECT i.id, i.store_id
        FROM invoices i
        JOIN stores s ON s.id = i.store_id
        WHERE i.invoice_number = ?
          AND TRIM(s.name) != ?
        ORDER BY i.id ASC
        LIMIT 1
        """,
        (invoice_number, UNKNOWN),
    )
    row = cur.fetchone()
    if not row:
        return None
    return int(row[0]), int(row[1])


def _merge_appendix_into_parent(
    cur: sqlite3.Cursor, appendix_invoice_id: int, parent_invoice_id: int
) -> None:
    cur.execute(
        "SELECT COALESCE(MAX(line_no), 0) FROM invoice_items WHERE invoice_id = ?",
        (parent_invoice_id,),
    )
    max_ln = int((cur.fetchone() or (0,))[0] or 0)

    cur.execute(
        """
        SELECT id FROM invoice_items
        WHERE invoice_id = ?
        ORDER BY COALESCE(line_no, 999999), id
        """,
        (appendix_invoice_id,),
    )
    item_ids = [int(r[0]) for r in cur.fetchall()]
    for i, iid in enumerate(item_ids, start=1):
        cur.execute(
            "UPDATE invoice_items SET invoice_id = ?, line_no = ? WHERE id = ?",
            (parent_invoice_id, max_ln + i, iid),
        )

    cur.execute(
        "SELECT notes, source_file, raw_text FROM invoices WHERE id = ?",
        (appendix_invoice_id,),
    )
    apx = cur.fetchone()
    cur.execute("SELECT notes FROM invoices WHERE id = ?", (parent_invoice_id,))
    pn = (cur.fetchone() or (None,))[0]
    if apx:
        ap_notes, ap_src, _ap_raw = apx[0], apx[1], apx[2]
        extra: list[str] = []
        if ap_src:
            extra.append(f"merged appendix source_file={ap_src!r}")
        if ap_notes:
            extra.append(f"appendix notes: {ap_notes}")
        if extra:
            note_parts: list[str] = []
            if pn:
                note_parts.append(str(pn))
            note_parts.extend(extra)
            merged = " | ".join(note_parts)
            cur.execute(
                "UPDATE invoices SET notes = ? WHERE id = ?",
                (merged[:500000], parent_invoice_id),
            )

    cur.execute("DELETE FROM invoices WHERE id = ?", (appendix_invoice_id,))
    _recompute_invoice_totals(cur, parent_invoice_id)


def _list_unknown_invoices(
    cur: sqlite3.Cursor,
) -> list[tuple[int, str, int, str | None]]:
    cur.execute(
        """
        SELECT i.id, i.invoice_number, i.store_id, i.raw_text
        FROM invoices i
        JOIN stores s ON s.id = i.store_id
        WHERE TRIM(s.name) = ?
        ORDER BY i.id ASC
        """,
        (UNKNOWN,),
    )
    return [
        (int(r[0]), str(r[1]), int(r[2]), r[3] if r[3] is not None else None)
        for r in cur.fetchall()
    ]


def _delete_orphan_unknown_stores(cur: sqlite3.Cursor) -> int:
    cur.execute(
        """
        DELETE FROM stores
        WHERE TRIM(name) = ?
          AND NOT EXISTS (SELECT 1 FROM invoices i WHERE i.store_id = stores.id)
        """,
        (UNKNOWN,),
    )
    return cur.rowcount if cur.rowcount is not None else 0


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    db_path = get_db_path()
    if not db_path.is_file():
        print(f"No database: {db_path}")
        return 1

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    unknown_rows = _list_unknown_invoices(cur)
    n_before = len(unknown_rows)
    parent_index = _parent_index_by_waybill(cur)
    fixed = 0
    skipped = 0
    skip_reasons: list[str] = []

    for inv_id, inv_no, _sid, raw in unknown_rows:
        parent: tuple[int, int] | None = None
        keys = _waybill_keys_for_row(inv_no, raw)
        for k in keys:
            hit = parent_index.get(k)
            if hit is not None and hit[0] != inv_id:
                parent = hit
                break
        if parent is None:
            parent = _find_parent_invoice(cur, inv_no)
        if parent is None:
            skipped += 1
            keys_hint = ", ".join(sorted(keys)[:3]) if keys else "(no waybill key)"
            skip_reasons.append(
                f"invoice id={inv_id} №{inv_no!r} keys={keys_hint!r}: no sibling with real store"
            )
            continue
        parent_id, _parent_store = parent
        if parent_id == inv_id:
            skipped += 1
            skip_reasons.append(f"invoice id={inv_id} №{inv_no!r}: parent is self (unexpected)")
            continue
        _merge_appendix_into_parent(cur, inv_id, parent_id)
        fixed += 1

    removed_stores = _delete_orphan_unknown_stores(cur)
    conn.commit()

    cur.execute(
        "SELECT COUNT(*) FROM invoices i JOIN stores s ON s.id = i.store_id WHERE TRIM(s.name) = ?",
        (UNKNOWN,),
    )
    remaining_unknown_invoices = int((cur.fetchone() or (0,))[0])

    print("=" * 60)
    print("stitch_appendices.py — summary")
    print("=" * 60)
    print(f"Unknown-buyer invoices seen:     {n_before}")
    print(f"Stitched (merged into parent): {fixed}")
    print(f"Skipped (no matching parent):  {skipped}")
    print(f"Orphan '(უცნობი მყიდველი)' store rows deleted: {removed_stores}")
    print(f"Remaining unknown-buyer invoices: {remaining_unknown_invoices}")
    if skip_reasons and skipped <= 30:
        print("-" * 60)
        for line in skip_reasons:
            print(f"  {line}")
    elif skip_reasons:
        print("-" * 60)
        for line in skip_reasons[:20]:
            print(f"  {line}")
        print(f"  … and {len(skip_reasons) - 20} more")

    print("=" * 60)
    print("Cleaned store list (name + invoice count)")
    print("=" * 60)
    cur.execute(
        """
        SELECT s.id, s.name, COUNT(i.id) AS n_inv
        FROM stores s
        LEFT JOIN invoices i ON i.store_id = s.id
        GROUP BY s.id, s.name
        ORDER BY s.name COLLATE NOCASE
        """
    )
    for sid, name, n_inv in cur.fetchall():
        flag = " <<< UNKNOWN PLACEHOLDER" if str(name).strip() == UNKNOWN else ""
        print(f"  {int(sid):5d}  {n_inv:4d} inv  {name!r}{flag}")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

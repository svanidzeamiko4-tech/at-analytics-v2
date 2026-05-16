"""
Product display normalization for analytics (OCR / table-noise variants).

- Defines ``product_merge_rules`` (m1 + optional m2, m3 must all appear as
  substrings in a cleaned label). Highest ``priority`` wins; ties break by
  longer combined pattern length.
- ``seed_product_merge_rules(conn)`` refreshes rule rows (idempotent).
- ``top_products_normalized_sql()`` returns SQL for the Top-N report.

Run (refresh rules + Top 10 table):
  python product_normalization.py

Sandwich bucket audit (French toast vs merged lines):
  python product_normalization.py --sandwich-audit
"""

from __future__ import annotations

import sqlite3
import sys

from database_init import get_db_path

CANONICAL_SANDWICH = "სენდვიჩ ტოსტი (470გრ პური)"
CANONICAL_FRENCH_TOAST = "ფრანგული ტოსტის პური"
FRENCH_TOAST_SUBSTR = "ფრანგული ტოსტის პური"

# (priority, canonical_name, m1, m2, m3) — all non-null parts must match as substrings.
_MERGE_RULES: list[tuple[int, str, str, str | None, str | None]] = [
    # --- ფრანგული ტოსტის პური (must beat sandwich: „ტოსტი“ ⊆ „ტოსტის“) ---
    (102, CANONICAL_FRENCH_TOAST, "ფრანგული ტოსტის", None, None),
    (102, CANONICAL_FRENCH_TOAST, "ფრანგული", "ტოსტის პური", None),
    (101, CANONICAL_FRENCH_TOAST, "ფრანგულ", "ტოსტის", None),
    (101, CANONICAL_FRENCH_TOAST, "ფრანგული", "ტოსტს პური", None),
    # --- სენდვიჩ ტოსტი family (470 / 47036 / table prefixes) ---
    (100, CANONICAL_SANDWICH, "სენდვიჩ ტოსტი", None, None),
    (100, CANONICAL_SANDWICH, "სეწდვიჩ ტოსტი", None, None),
    (100, CANONICAL_SANDWICH, "სენდვინ ტოსტი", None, None),
    # --- პრემიუმ კლასი (მზესუმზირით + common OCR vowel swaps) ---
    (95, "პრემიუმ კლასი (პური მზესუმზირით 400გრ)", "პრემიუმკლასი", "მზესუმზირით", None),
    (95, "პრემიუმ კლასი (პური მზესუმზირით 400გრ)", "პრემიუმკლასი", "მხესუმზირით", None),
    (95, "პრემიუმ კლასი (პური მზესუმზირით 400გრ)", "პრემიუმკლასი", "მდესუმზირით", None),
    (94, "პრემიუმ კლასი (პური მზესუმზირით 400გრ)", "პრემიუმ კლასი", "მზესუმზირით", None),
    (94, "პრემიუმ კლასი (პური მზესუმზირით 400გრ)", "პრემიუმ კლასი", "მხესუმზირით", None),
    (94, "პრემიუმ კლასი (პური მზესუმზირით 400გრ)", "პრემიუმ კლასი", "მდესუმზირით", None),
    (93, "პრემიუმ კლასი (პური მზესუმზირით 400გრ)", "პრემიუმ კლასი", "მზესუმზირით", "47ო"),
    (93, "პრემიუმ კლასი (პური მზესუმზირით 400გრ)", "პრემიუმ", "მზესუმზირით", "400"),
    # --- Other obvious splits from table / OCR noise ---
    (90, "კულიჩი (470გრ)", "კულიჩი", "470", None),
    (90, "კულიჩი (470გრ)", "კულიჩ", "470", None),
    (90, "კულიჩი (470გრ)", "კულიჩი", "47ო", None),
    (90, "ჰამბურგერის პურები 320 გრ", "ჰამბურგერის", "320", None),
    (88, "400 გრ დიეტა, ქატოს პური", "დიეტა", "ქატოს", None),
]


def ensure_merge_rules_schema(cur: sqlite3.Cursor) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS product_merge_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            priority INTEGER NOT NULL DEFAULT 0,
            canonical_name TEXT NOT NULL,
            m1 TEXT NOT NULL,
            m2 TEXT,
            m3 TEXT,
            notes TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_product_merge_priority
        ON product_merge_rules(priority DESC)
        """
    )


def seed_product_merge_rules(cur: sqlite3.Cursor) -> int:
    ensure_merge_rules_schema(cur)
    cur.execute("DELETE FROM product_merge_rules")
    n = 0
    for prio, canon, a, b, c in _MERGE_RULES:
        cur.execute(
            """
            INSERT INTO product_merge_rules
                (priority, canonical_name, m1, m2, m3)
            VALUES (?, ?, ?, ?, ?)
            """,
            (prio, canon, a, b, c),
        )
        n += 1
    return n


def _norm_label_sql() -> str:
    """SQLite expression: strip pipes, fix common digit typo, collapse runs of spaces."""
    # char(124) = '|'
    x = "TRIM(COALESCE(p.name, ii.description, ''))"
    x = f"REPLACE({x}, char(124), ' ')"
    x = f"REPLACE({x}, '47036', '470')"
    for _ in range(4):
        x = f"REPLACE({x}, '  ', ' ')"
    return x


def items_and_tagged_ctes_sql() -> str:
    """``WITH items AS (...) , tagged AS (...)`` — same logic as the Top products report."""
    norm = _norm_label_sql()
    return f"""
WITH items AS (
    SELECT
        ii.id AS item_id,
        ii.quantity,
        ii.line_total,
        TRIM(COALESCE(p.name, ii.description, '')) AS raw_display,
        {norm} AS norm_label
    FROM invoice_items ii
    LEFT JOIN products p ON p.id = ii.product_id
),
tagged AS (
    SELECT
        i.item_id,
        i.quantity,
        i.line_total,
        i.raw_display,
        (
            SELECT r.canonical_name
            FROM product_merge_rules r
            WHERE instr(i.norm_label, r.m1) > 0
              AND (r.m2 IS NULL OR instr(i.norm_label, r.m2) > 0)
              AND (r.m3 IS NULL OR instr(i.norm_label, r.m3) > 0)
            ORDER BY
                r.priority DESC,
                length(r.m1)
                    + length(COALESCE(r.m2, ''))
                    + length(COALESCE(r.m3, '')) DESC,
                r.id DESC
            LIMIT 1
        ) AS canon
    FROM items i
)
""".strip()


def top_products_normalized_sql(limit: int = 10) -> str:
    return f"""
{items_and_tagged_ctes_sql()},
rolled AS (
    SELECT
        COALESCE(canon, raw_display) AS product,
        quantity,
        line_total
    FROM tagged
)
SELECT
    product,
    ROUND(SUM(quantity), 4) AS total_quantity,
    ROUND(SUM(COALESCE(line_total, 0)), 2) AS total_amount_gel
FROM rolled
GROUP BY product
ORDER BY SUM(quantity) DESC, SUM(COALESCE(line_total, 0)) DESC
LIMIT {int(limit)}
"""


def run_top_report(conn: sqlite3.Cursor, limit: int = 10) -> list[sqlite3.Row]:
    conn.execute(top_products_normalized_sql(limit))
    return list(conn.fetchall())


def sandwich_bucket_audit(cur: sqlite3.Cursor) -> None:
    """Print French-toast totals vs sandwich merge (stdout)."""
    cte = items_and_tagged_ctes_sql()
    cur.execute(
        f"""
        {cte}
        SELECT
            COUNT(*) AS line_rows,
            ROUND(SUM(quantity), 4) AS total_qty,
            SUM(CASE WHEN canon = ? THEN 1 ELSE 0 END) AS rows_classed_as_sandwich,
            SUM(CASE WHEN canon IS NULL OR canon != ? THEN 1 ELSE 0 END) AS rows_not_sandwich
        FROM tagged
        WHERE instr(raw_display, ?) > 0
        """,
        (CANONICAL_SANDWICH, CANONICAL_SANDWICH, FRENCH_TOAST_SUBSTR),
    )
    fr = cur.fetchone()
    print("=== Rows whose raw text contains 'ფრანგული ტოსტის პური' ===")
    print(f"  Invoice line rows: {fr[0]}")
    print(f"  Total quantity:     {fr[1]}")
    print(
        f"  Of those, classified as canonical '{CANONICAL_SANDWICH}': {fr[2]} "
        f"(should be 0)"
    )
    print(
        f"  Of those, NOT in sandwich bucket (NULL or other canon): {fr[3]}"
    )

    cur.execute(
        f"""
        {cte}
        SELECT raw_display, canon, ROUND(SUM(quantity), 4) AS qty
        FROM tagged
        WHERE instr(raw_display, ?) > 0
        GROUP BY raw_display, canon
        ORDER BY qty DESC
        """,
        (FRENCH_TOAST_SUBSTR,),
    )
    print()
    print("=== Same rows: raw_display + resolved canon + qty ===")
    for raw, canon, qty in cur.fetchall():
        c = canon if canon is not None else "(no rule — raw name kept)"
        print(f"  qty={qty:>8}  canon={c!r}")
        print(f"         raw={raw!r}")

    cur.execute(
        f"""
        {cte}
        SELECT raw_display, COUNT(*) AS n_lines, ROUND(SUM(quantity), 4) AS qty
        FROM tagged
        WHERE canon = ?
        GROUP BY raw_display
        ORDER BY qty DESC, raw_display
        """,
        (CANONICAL_SANDWICH,),
    )
    rows = cur.fetchall()
    total = sum(r[2] for r in rows)
    print()
    print(f"=== All raw descriptions merged into '{CANONICAL_SANDWICH}' ===")
    print(f"  Distinct raw strings: {len(rows)}")
    print(f"  Sum of quantities:    {total}")
    print()
    for raw, nlines, qty in rows:
        print(f"  qty={qty:>10}  lines={nlines:>4}  {raw!r}")


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    db = get_db_path()
    if not db.is_file():
        print(f"No database: {db}")
        return 1

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    n = seed_product_merge_rules(cur)
    conn.commit()
    print(f"product_merge_rules seeded: {n} row(s)")

    cur.execute(top_products_normalized_sql(10))
    rows = cur.fetchall()
    conn.close()

    print()
    print("| Rank | Product (normalized) | Total Qty | Total Amount (GEL) |")
    print("|------|----------------------|-----------|---------------------|")
    for i, r in enumerate(rows, 1):
        name = (r["product"] or "").replace("|", "\\|").replace("\n", " ")
        print(
            f"| {i} | {name} | {r['total_quantity']} | {r['total_amount_gel']} |"
        )
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--sandwich-audit":
        if sys.platform == "win32":
            try:
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
        db = get_db_path()
        if not db.is_file():
            raise SystemExit(f"No database: {db}")
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        seed_product_merge_rules(cur)
        conn.commit()
        sandwich_bucket_audit(cur)
        conn.close()
        raise SystemExit(0)
    raise SystemExit(main())

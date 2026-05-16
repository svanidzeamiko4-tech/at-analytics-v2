"""
Split a multi-page PDF into one file per page (invoice_1.pdf … invoice_N.pdf).

Default source: ``200.pdf`` in this script's directory, or ``processed/200.pdf``.
Then (when run as main): clear invoice tables, move splits into the project root
so ``main_processor.py`` ingests each page as its own invoice.

Usage:
  python split_pdf.py
  python split_pdf.py path/to/source.pdf
  python split_pdf.py --split-only
"""

from __future__ import annotations

import re
import shutil
import sqlite3
import sys
from pathlib import Path

import fitz  # PyMuPDF


def _resolve_source_pdf(root: Path, argv: list[str]) -> Path:
    if len(argv) > 1 and not argv[1].startswith("-"):
        p = Path(argv[1]).expanduser()
        if not p.is_absolute():
            p = (root / p).resolve()
        else:
            p = p.resolve()
        if p.is_file():
            return p
        raise FileNotFoundError(p)
    for candidate in (root / "200.pdf", root / "processed" / "200.pdf"):
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        f"No 200.pdf in {root} or {root / 'processed'}. Pass path: python split_pdf.py <file.pdf>"
    )


def split_pdf_to_folder(
    source_pdf: Path,
    out_dir: Path,
    *,
    name_prefix: str = "invoice_",
) -> int:
    """
    Write ``{name_prefix}{1..N}.pdf`` (one page each) into ``out_dir``.
    Returns page count ``N``.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob(f"{name_prefix}*.pdf"):
        try:
            old.unlink()
        except OSError:
            pass

    doc = fitz.open(source_pdf)
    try:
        n = doc.page_count
        for i in range(n):
            single = fitz.open()
            try:
                single.insert_pdf(doc, from_page=i, to_page=i)
                out_path = out_dir / f"{name_prefix}{i + 1}.pdf"
                single.save(out_path)
            finally:
                single.close()
    finally:
        doc.close()
    return n


def clear_invoice_tables(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("DELETE FROM invoice_items")
        conn.execute("DELETE FROM invoices")
        conn.execute("DELETE FROM stores")
        conn.commit()
    finally:
        conn.close()


def _invoice_pdf_sort_key(p: Path) -> int:
    m = re.search(r"invoice_(\d+)\.pdf$", p.name, re.IGNORECASE)
    return int(m.group(1)) if m else 0


def move_splits_to_project_root(split_dir: Path, project_root: Path) -> int:
    """Move ``invoice_*.pdf`` from ``split_dir`` to ``project_root``. Returns count moved."""
    files = sorted(split_dir.glob("invoice_*.pdf"), key=_invoice_pdf_sort_key)
    moved = 0
    for src in files:
        dest = project_root / src.name
        if dest.exists():
            dest.unlink()
        shutil.move(str(src), str(dest))
        moved += 1
    try:
        split_dir.rmdir()
    except OSError:
        pass
    return moved


def main() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    root = Path(__file__).resolve().parent
    split_only = "--split-only" in sys.argv
    argv = [a for a in sys.argv if a != "--split-only"]

    source = _resolve_source_pdf(root, argv)
    out_dir = root / "split_invoices"

    print(f"Source: {source}")
    n = split_pdf_to_folder(source, out_dir)
    print(f"Split into {n} file(s) under {out_dir}")

    if split_only:
        return

    db_path = root / "amiko_v3.db"
    if db_path.is_file():
        clear_invoice_tables(db_path)
        print(f"Cleared invoice_items, invoices, stores in {db_path.name}")
    else:
        print(f"Warning: no database at {db_path} — skip clear")

    m = move_splits_to_project_root(out_dir, root)
    print(f"Moved {m} file(s) to {root}")
    print("Next: python main_processor.py")


if __name__ == "__main__":
    main()

"""
Smoke test: run OCR/PDF extraction on a real PDF next to this script.

Usage:
  python test_run.py
  python test_run.py path/to/waybill.pdf
  python test_run.py path/to/waybill.pdf --dump-buyer-region
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from ocr_engine import preview_rs_buyer_header_text, process_pdf
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Missing Python packages. From this folder run:\n"
        "  pip install -r requirements.txt\n"
        f"({exc})"
    ) from exc


def _ensure_utf8_stdout() -> None:
    if sys.platform != "win32":
        return
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _parse_cli() -> tuple[Path | None, bool]:
    """Return (optional pdf path, dump_buyer_region)."""
    dump = False
    paths: list[str] = []
    for a in sys.argv[1:]:
        if a == "--dump-buyer-region":
            dump = True
        elif not a.startswith("-"):
            paths.append(a)
    p: Path | None = None
    if paths:
        p = Path(paths[0]).expanduser().resolve()
    return p, dump


def _pick_default_pdf() -> Path:
    root = Path(__file__).resolve().parent
    pdfs = sorted(root.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(
            f"No PDF found in {root}. Add a .pdf file here or run:\n"
            f"  python test_run.py path\\to\\file.pdf"
        )
    return pdfs[0]


def main() -> None:
    _ensure_utf8_stdout()
    pdf_arg, dump_buyer_region = _parse_cli()
    pdf = pdf_arg if pdf_arg is not None else _pick_default_pdf()
    if not pdf.is_file():
        raise SystemExit(f"Not a file: {pdf}")

    db = Path(__file__).resolve().parent / "amiko_v3.db"
    result = process_pdf(
        pdf,
        stores_db_path=db if db.is_file() else None,
    )

    print("=== PDF ===")
    print(pdf)
    print()
    print("=== Extracted ===")
    print(f"store_name:       {result.store_name!r}")
    print(f"buyer_address:    {result.buyer_address!r}")
    print(f"origin_address:   {result.origin_address!r}")
    print(f"store_branch_address: {result.store_branch_address!r}")
    print(f"invoice_time:     {result.invoice_time!r}")
    print()
    print("=== First 3 products ===")
    for i, row in enumerate(result.products[:3], start=1):
        print(f"  {i}. name={row.name!r} qty={row.quantity!r} price={row.price!r}")
    if not result.products:
        print("  (no product rows parsed)")
    print()
    print("=== Fuzzy match (stores in amiko_v3.db) ===")
    if not db.is_file():
        print(f"  Database not found: {db} — fuzzy match skipped.")
    elif result.matched_store_id is not None:
        print("  SUCCESS: match above threshold")
        print(f"  matched_store_id:   {result.matched_store_id}")
        print(f"  matched_store_name: {result.matched_store_name!r}")
        print(f"  fuzzy_match_score:  {result.fuzzy_match_score:.4f}")
    else:
        print("  No match >= threshold (or stores table empty).")
        print(f"  best_fuzzy_score: {result.fuzzy_match_score:.4f}")
        print(f"  cleaned name used: {result.store_name!r}")

    if result.warnings:
        print()
        print("=== Warnings ===")
        for w in result.warnings:
            print(f"  - {w}")

    if dump_buyer_region:
        print()
        print("=== Raw buyer header region (მყიდველის … სასაქონლო ზედნადების ცხრილი) ===")
        region = preview_rs_buyer_header_text(result.raw_text)
        if region:
            print(region)
        else:
            print(
                "(Could not slice region — missing buyer caption or "
                "სასაქონლო ზედნადების ცხრილი anchor in text.)"
            )


if __name__ == "__main__":
    main()

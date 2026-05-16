"""
OCR / PDF text pipeline for Amiko Analytics V3.

- Digital PDFs: pdfplumber for text, table extraction, and word geometry.
- Scanned pages or broken text layers (e.g. ``(cid:####)`` placeholders): PyMuPDF
  render + pytesseract. Tesseract executable:
  ``C:\\Program Files\\Tesseract-OCR\\tesseract.exe`` (``kat`` + optional langs).

Large PDFs are handled **page-by-page**: PyMuPDF opens the file once; each page is
rasterized to PNG bytes, OCR'd, then released (see ``iter_fitz_page_png_bytes``).
pdfplumber / OCR errors on a single page are logged and skipped so other pages
still contribute to ``raw_text``.

Georgian waybills (სასაქონლო ზედნადები): buyer/store and address rules are
tuned for common RS.ge PDF layouts; adjust regexes if a supplier changes.
"""

from __future__ import annotations

import difflib
import io
import logging
import re
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

import fitz  # PyMuPDF
import pdfplumber
import pytesseract
from PIL import Image

# RS.ge PDFs often map glyphs to (cid:####) when ToUnicode is missing — OCR reads pixels instead.
pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass
class ProductRow:
    name: str
    quantity: str
    price: str


@dataclass
class PdfProcessResult:
    waybill_number: str | None
    store_name: str | None
    """Store / buyer name after cleaning (S/N stripped)."""
    store_name_raw: str | None = None
    """Original parsed name before aggressive cleaning."""
    date: str | None = None
    invoice_time: str | None = None
    buyer_address: str | None = None
    """Address-like lines from the buyer block (cities / street cues)."""
    products: list[ProductRow] = field(default_factory=list)
    raw_text: str = ""
    pages_total: int = 0
    pages_ocrd: int = 0
    tables_found: int = 0
    warnings: list[str] = field(default_factory=list)
    matched_store_id: int | None = None
    """If fuzzy match against ``stores`` >= threshold."""
    matched_store_name: str | None = None
    fuzzy_match_score: float = 0.0
    origin_address: str | None = None
    """Field 7: ტრანსპორტირების დაწყების ადგილი — branch #code (seller/origin)."""
    store_branch_address: str | None = None
    """Correct store/branch address regardless of invoice type (return vs delivery)."""


# ---------------------------------------------------------------------------
# PDF: digital text + optional OCR per page
# ---------------------------------------------------------------------------

_DEFAULT_MIN_CHARS = 48
_DEFAULT_OCR_DPI = 220
_DEFAULT_TESS_LANG = "kat+eng"
_DEFAULT_TESS_CONFIG = r"--oem 3 --psm 6"
_DEFAULT_FUZZY_THRESHOLD = 0.9


def _ensure_georgian_kat_lang(lang: str) -> str:
    """Tesseract language string must include ``kat`` for Georgian text."""
    if not lang or "kat" not in lang.replace(" ", "").casefold():
        return f"kat+{lang}".strip("+") if lang else "kat"
    return lang


def _text_has_cid_placeholders(text: str) -> bool:
    return "(cid:" in (text or "").casefold()


def _needs_tesseract_fallback(text: str, min_chars: int) -> bool:
    """
    Use raster OCR when pdfplumber text is too thin, missing, or uses (cid:)
    placeholder glyphs (broken ToUnicode / embedded subset fonts).
    """
    stripped = re.sub(r"\s+", "", text or "")
    if len(stripped) < min_chars:
        return True
    if _text_has_cid_placeholders(text):
        return True
    return False


def _ocr_png_bytes(png_bytes: bytes, lang: str, tesseract_config: str) -> str:
    """Run Tesseract on a single PNG byte string; caller owns memory discipline."""
    img = Image.open(io.BytesIO(png_bytes))
    try:
        return pytesseract.image_to_string(
            img, lang=lang, config=tesseract_config
        ).strip()
    finally:
        img.close()


def _render_fitz_page_png(
    doc: fitz.Document, page_index: int, dpi: int
) -> tuple[bytes | None, str | None]:
    """Rasterize one page to PNG bytes, or return (None, error_message)."""
    try:
        page = doc.load_page(page_index)
        mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        try:
            return pix.tobytes("png"), None
        finally:
            pix = None  # type: ignore[assignment]
    except Exception as exc:
        return None, str(exc)


def iter_fitz_page_png_bytes(
    pdf_path: str | Path, dpi: int
) -> Iterator[tuple[int, bytes | None, str | None]]:
    """
    Yield ``(page_index, png_bytes_or_None, error_or_None)`` for each page.

    Opens the PDF once with PyMuPDF; only one page's pixmap bytes is materialized
    per iteration (suitable for large / many-page documents).
    """
    path = Path(pdf_path).expanduser().resolve()
    doc = fitz.open(path)
    try:
        for i in range(doc.page_count):
            data, err = _render_fitz_page_png(doc, i, dpi)
            yield i, data, err
    finally:
        doc.close()


def _page_text_and_tables(
    page: pdfplumber.page.Page,
) -> tuple[str, list[list[list[str | None]]]]:
    text = (page.extract_text() or "").strip()
    tables: list[list[list[str | None]]] = []
    try:
        raw_tables = page.extract_tables(
            table_settings={
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
                "intersection_tolerance": 5,
            }
        )
    except Exception:
        raw_tables = page.extract_tables()

    if raw_tables:
        for t in raw_tables:
            if t:
                tables.append(t)
    return text, tables


def _ocr_page_with_tesseract(
    pdf_path: Path,
    page_index: int,
    dpi: int,
    lang: str,
    tesseract_config: str,
) -> str:
    """OCR a single page when no shared :class:`fitz.Document` is available."""
    doc = fitz.open(pdf_path)
    try:
        png, err = _render_fitz_page_png(doc, page_index, dpi)
        if err or png is None:
            raise RuntimeError(err or "render failed")
        return _ocr_png_bytes(png, lang, tesseract_config)
    finally:
        doc.close()


def _fitz_fallback_page_texts(
    doc: fitz.Document,
    min_chars_for_digital: int,
    ocr_dpi: int,
    ocr_lang: str,
    tesseract_config: str,
    warnings: list[str],
) -> tuple[list[str], int, int]:
    """If pdfplumber cannot open the file, extract text / OCR page-by-page with PyMuPDF."""
    page_texts: list[str] = []
    pages_ocrd = 0
    n = doc.page_count
    for i in range(n):
        plumb_text = ""
        try:
            plumb_text = (doc.load_page(i).get_text() or "").strip()
        except Exception as exc:
            msg = f"Page {i + 1} PyMuPDF get_text failed: {exc}"
            _log.warning(msg, exc_info=True)
            warnings.append(msg)
        use_ocr = _needs_tesseract_fallback(plumb_text, min_chars_for_digital)
        text = plumb_text
        if use_ocr:
            try:
                png, err = _render_fitz_page_png(doc, i, ocr_dpi)
                if err or png is None:
                    raise RuntimeError(err or "render failed")
                text = _ocr_png_bytes(png, ocr_lang, tesseract_config)
                pages_ocrd += 1
            except Exception as exc:
                msg = f"Page {i + 1} OCR failed: {exc}"
                _log.warning(msg, exc_info=True)
                warnings.append(msg)
                text = plumb_text or ""
        page_texts.append(text)
    return page_texts, pages_ocrd, n


def process_pdf(
    pdf_path: str | Path,
    *,
    min_chars_for_digital: int = _DEFAULT_MIN_CHARS,
    ocr_dpi: int = _DEFAULT_OCR_DPI,
    ocr_lang: str = _DEFAULT_TESS_LANG,
    tesseract_config: str = _DEFAULT_TESS_CONFIG,
    stores_db_path: str | Path | None = None,
    fuzzy_threshold: float = _DEFAULT_FUZZY_THRESHOLD,
) -> PdfProcessResult:
    """
    Extract waybill, buyer/store, date/time, buyer-side address, and products.

    Pages are handled one at a time: pdfplumber failures and OCR failures on a
    single page are logged and skipped so the rest of a long document can still
    be processed. PyMuPDF is opened once for raster OCR to avoid reopening the
    file per page.

    ``stores_db_path`` defaults to ``amiko_v3.db`` next to this file when the
    file exists; fuzzy matching is skipped if the DB is missing or empty.
    """
    path = Path(pdf_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)

    ocr_lang = _ensure_georgian_kat_lang(ocr_lang)

    warnings: list[str] = []
    page_texts: list[str] = []
    all_tables: list[list[list[str | None]]] = []
    pages_ocrd = 0
    first_page_words: list[dict[str, Any]] = []
    first_w = first_h = 0.0
    pages_total = 0
    used_plumber = False

    fitz_doc: fitz.Document | None = None
    try:
        try:
            fitz_doc = fitz.open(path)
        except Exception as exc:
            msg = f"PyMuPDF open failed: {exc}"
            _log.warning(msg, exc_info=True)
            warnings.append(msg)
            fitz_doc = None

        try:
            with pdfplumber.open(path) as pdf:
                pages_total = len(pdf.pages)
                for i, page in enumerate(pdf.pages):
                    plumb_text = ""
                    plumb_tables: list[list[list[str | None]]] = []
                    try:
                        if i == 0:
                            first_w, first_h = float(page.width), float(page.height)
                            try:
                                first_page_words = (
                                    page.extract_words(
                                        use_text_flow=True,
                                        keep_blank_chars=False,
                                    )
                                    or []
                                )
                            except Exception as exc:
                                w0 = f"Page 1 extract_words failed: {exc}"
                                _log.warning(w0, exc_info=True)
                                warnings.append(w0)
                                first_page_words = []
                        plumb_text, plumb_tables = _page_text_and_tables(page)
                    except Exception as exc:
                        msg = f"Page {i + 1} pdfplumber extract failed: {exc}"
                        _log.warning(msg, exc_info=True)
                        warnings.append(msg)

                    text = plumb_text
                    use_ocr = _needs_tesseract_fallback(text, min_chars_for_digital)
                    if use_ocr:
                        try:
                            if fitz_doc is not None:
                                png, err = _render_fitz_page_png(fitz_doc, i, ocr_dpi)
                                if err or png is None:
                                    raise RuntimeError(err or "render failed")
                                text = _ocr_png_bytes(png, ocr_lang, tesseract_config)
                            else:
                                text = _ocr_page_with_tesseract(
                                    path, i, ocr_dpi, ocr_lang, tesseract_config
                                )
                            pages_ocrd += 1
                        except Exception as exc:
                            msg = f"Page {i + 1} OCR failed: {exc}"
                            _log.warning(msg, exc_info=True)
                            warnings.append(msg)
                            text = plumb_text or ""
                    else:
                        all_tables.extend(plumb_tables)

                    page_texts.append(text)
                used_plumber = True
        except Exception as exc:
            msg = f"pdfplumber open/read failed: {exc}"
            _log.warning(msg, exc_info=True)
            warnings.append(msg)
            used_plumber = False

        if not used_plumber:
            if fitz_doc is None:
                raise RuntimeError(
                    f"Cannot read PDF with pdfplumber or PyMuPDF: {path}"
                )
            page_texts, pages_ocrd, pages_total = _fitz_fallback_page_texts(
                fitz_doc,
                min_chars_for_digital,
                ocr_dpi,
                ocr_lang,
                tesseract_config,
                warnings,
            )
            all_tables = []

    finally:
        if fitz_doc is not None:
            fitz_doc.close()

    raw_text = "\n\n".join(page_texts)
    waybill = _extract_waybill(raw_text)
    store_raw = _extract_store_name(raw_text, first_page_words, first_w, first_h)
    store_clean = clean_store_name(store_raw)
    if not (store_clean or "").strip():
        excerpt = _first_page_top_excerpt(raw_text)
        msg = (
            "store_name unresolved after all fallbacks; "
            "first-page OCR excerpt (start of document) follows:\n"
            f"{excerpt}"
        )
        warnings.append(msg)
        _log.warning(msg)
    date = _extract_date_preferred(raw_text)
    inv_time = _extract_invoice_time(raw_text, date)
    buyer_block = _extract_buyer_block_text(raw_text)
    header_region = _extract_header_before_line_items(raw_text)
    buyer_addr = (
        _extract_buyer_address_rs_line_order(raw_text)
        or _extract_buyer_addresses(buyer_block)
        or _extract_buyer_addresses(header_region)
        or _extract_buyer_addresses(raw_text)
    )
    buyer_addr = _apply_ocr_corrections_address(buyer_addr)

    origin_addr = _extract_origin_address(raw_text)
    origin_addr = _apply_ocr_corrections_address(origin_addr)

    store_branch_addr = _extract_store_branch_address(raw_text)
    store_branch_addr = _apply_ocr_corrections_address(store_branch_addr)

    products = _products_from_tables(all_tables)
    bundled = _products_from_bundled_ocr_lines(raw_text)
    if bundled and (pages_ocrd > 0 or not products):
        products = bundled
    elif not products:
        products = _products_from_text_lines(raw_text)

    db_path = _resolve_stores_db(stores_db_path)
    matched_id, matched_name, fuzzy_score = _fuzzy_match_store(
        store_clean, db_path, fuzzy_threshold
    )

    return PdfProcessResult(
        waybill_number=waybill,
        store_name=store_clean,
        store_name_raw=store_raw,
        date=date,
        invoice_time=inv_time,
        buyer_address=buyer_addr,
        products=products,
        raw_text=raw_text,
        pages_total=pages_total,
        pages_ocrd=pages_ocrd,
        tables_found=len(all_tables),
        warnings=warnings,
        matched_store_id=matched_id,
        matched_store_name=matched_name,
        fuzzy_match_score=fuzzy_score,
        origin_address=origin_addr,
        store_branch_address=store_branch_addr,
    )


def _resolve_stores_db(stores_db_path: str | Path | None) -> Path | None:
    if stores_db_path is not None:
        p = Path(stores_db_path).expanduser().resolve()
        return p if p.is_file() else None
    default = Path(__file__).resolve().parent / "amiko_v3.db"
    return default if default.is_file() else None


# ---------------------------------------------------------------------------
# RS.ge line order (2.pdf):
# - Buyer დასახელება label → legal name on the line above (შპს/სს).
# - Buyer physical address must come from **transport completion** (მიმღების
#   მხარე): text under ``ტრანსპორტირების დასრულების ადგილი``, not the first
#   address under ``დაწყების ადგილი`` (that is the seller / origin).
# ---------------------------------------------------------------------------


def _rs_source_lines(full_text: str) -> list[str]:
    """Non-empty lines in reading order (OCR / pdfplumber text)."""
    lines: list[str] = []
    for raw in full_text.replace("\u00a0", " ").replace("\r\n", "\n").split("\n"):
        ln = re.sub(r"[ \t]+", " ", raw.strip())
        if ln:
            lines.append(ln)
    return lines


_BUYER_DASAKHLEBA_LABEL_RE = re.compile(
    r"მყიდველის\s*\([^)]*მიმღების[^)]*\)\s*დასახელება",
    re.UNICODE | re.IGNORECASE,
)


def _find_buyer_dasakhleba_label_index(lines: list[str]) -> int | None:
    for i, ln in enumerate(lines):
        if _BUYER_DASAKHLEBA_LABEL_RE.search(ln):
            return i
        if (
            "მყიდველის" in ln
            and "მიმღების" in ln
            and "დასახელება" in ln
        ):
            return i
    return None


def _line_has_shps_or_ss(line: str) -> bool:
    if "შპს" in line:
        return True
    if re.search(r"(^|\s)სს\s", line) or line.startswith("სს "):
        return True
    s = line.strip()
    # ``სსზღაპარი``-style OCR (no space after ``სს``).
    if len(s) > 3 and s.startswith("სს") and s[2] != "ს":
        return True
    return False


def _prefer_buyer_shps_on_glued_line(line: str) -> str:
    """
    If OCR glues seller + buyer on one line (two ``შპს``), keep the last entity
    (buyer is below seller on RS.ge forms).
    """
    s = line.strip()
    if s.count("შპს") >= 2:
        i = s.rfind("შპს")
        return s[i:].strip()
    return s


# Known LT Distribution / seller fragments that sometimes remain in the buyer cell after OCR.
_SELLER_NAME_NOISE = re.compile(
    r"შპს\s*ელთი\s*დისტრიბუცია|ელთი\s*დისტრიბუცია|200249043",
    re.UNICODE,
)


def _isolate_buyer_store_name_from_line(line: str) -> str:
    """
    Isolate buyer legal name when glued with seller on one RS.ge row.

    Typical pattern: ``[seller შპს …][seller 9-digit id][buyer შპს|სს …]``.
    Take text starting at the buyer ``შპს`` / ``სს`` that follows the first
    standalone 9-digit block (seller taxpayer id).
    """
    s = _prefer_buyer_shps_on_glued_line(line.strip())
    if not s:
        return s
    # Seller id → buyer legal prefix (შპს or სს).
    m = re.search(r"(?<![0-9])\d{9}(?![0-9])\s+((?:შპს|სს)\s)", s)
    if m:
        # Group 1 is the outer ``((?:შპს|სს)\\s)`` — inner ``(?:...)`` is non-capturing.
        return s[m.start(1) :].strip()
    return s


def _is_transport_or_seller_glue(line: str) -> bool:
    """Reject bbox lines that are transport / merged header, not a store name row."""
    t = re.sub(r"\s+", " ", line.strip())
    if not t:
        return True
    if re.search(r"ტრანსპორტირების\s*სახე", t):
        return True
    if "გამყიდველის" in t and "მყიდველის" in t and "დასახელება" in t and len(t) > 100:
        return True
    return False


def _store_name_line_above_buyer_dasakhleba(lines: list[str]) -> str | None:
    """
    First line *above* ``მყიდველის (მიმღების) დასახელება`` that contains ``შპს`` or ``სს``.
    """
    idx = _find_buyer_dasakhleba_label_index(lines)
    if idx is None:
        return None
    upper = max(0, idx - 30)
    for k in range(idx - 1, upper - 1, -1):
        if k < 0:
            break
        ln = lines[k]
        if re.fullmatch(r"[\d\s/\-]+", ln.strip()):
            continue
        if _line_has_shps_or_ss(ln):
            return _isolate_buyer_store_name_from_line(ln)
    return None


def _skip_seller_keyword_line_for_buyer(ln: str) -> bool:
    """Drop obvious seller / LT rows when hunting for the buyer legal name."""
    t = ln.strip()
    if "ელთი" in t and "დისტრიბუცია" in t:
        return True
    if "200249043" in t and "მიმღების" not in t:
        return True
    if re.search(r"გამყიდველის\s*\(", t) and "მიმღების" not in t:
        return True
    return False


def _store_name_buyer_adjacent_scan(lines: list[str]) -> str | None:
    """
    If the name is not on the line directly above the buyer caption, scan a few
    lines above and below the buyer ``დასახელება`` row (OCR often shifts the row).
    """
    idx = _find_buyer_dasakhleba_label_index(lines)
    if idx is None:
        return None
    best: str | None = None
    best_sc = -1e9
    for d in range(-8, 12):
        k = idx + d
        if k < 0 or k >= len(lines):
            continue
        ln = lines[k]
        if not _line_has_shps_or_ss(ln):
            continue
        if _skip_seller_keyword_line_for_buyer(ln):
            continue
        if re.fullmatch(r"[\d\s/\-]+", ln.strip()):
            continue
        isolated = _isolate_buyer_store_name_from_line(ln)
        if _is_store_name_junk_line(isolated) and not _looks_like_legal_entity_line(isolated):
            continue
        sc = _score_store_candidate(isolated)
        if sc > best_sc:
            best_sc = sc
            best = isolated
    if best is not None and best_sc >= 0.25:
        return best
    return None


def _first_page_text_slice(raw_text: str) -> str:
    """First logical page (split PDFs are usually one page per file)."""
    parts = raw_text.split("\n\n")
    return parts[0] if parts else raw_text


def _first_page_top_excerpt(raw_text: str, *, max_chars: int = 4500) -> str:
    """First ~40 lines of page 1 (for debug when store name is missing)."""
    page0 = _first_page_text_slice(raw_text)
    lines = _rs_source_lines(page0)
    if not lines:
        return page0[:max_chars]
    n = min(len(lines), 45)
    chunk = "\n".join(lines[:n])
    if len(chunk) > max_chars:
        return chunk[:max_chars] + "\n… [truncated]"
    return chunk


def _extract_store_name_pre_table_keyword(lines: list[str]) -> str | None:
    """
    Pick the strongest ``შპს`` / ``სს`` line in the **header** above the line-items
    grid. ``top half`` alone misses the buyer when OCR puts many header lines first
    or the legal name sits just above ``სასაქონლო ზედნადების ცხრილი``.
    """
    if not lines:
        return None
    end = len(lines)
    for i, ln in enumerate(lines):
        if "სასაქონლო" in ln and "ზედნადების" in ln and ("ცხრილი" in ln or "ცხრილ" in ln):
            end = i
            break
    if end == len(lines):
        for i, ln in enumerate(lines):
            if i < 8:
                continue
            if re.search(r"\|\s*\d", ln) and len(ln) > 18:
                end = i
                break
    # Cap depth so we do not wander into product rows if the grid caption was missed.
    end = min(end, 55, len(lines))
    band = lines[:max(1, end)]
    best: str | None = None
    best_sc = -1e9
    for ln in band:
        if _skip_seller_keyword_line_for_buyer(ln):
            continue
        if not _line_has_shps_or_ss(ln):
            continue
        if _is_store_name_junk_line(ln) and not _looks_like_legal_entity_line(ln):
            continue
        isolated = _isolate_buyer_store_name_from_line(ln)
        if _is_store_name_junk_line(isolated) and not _looks_like_legal_entity_line(isolated):
            continue
        sc = _score_store_candidate(isolated)
        if sc > best_sc:
            best_sc = sc
            best = isolated
    if best is not None and best_sc >= 0.4:
        return best
    return None


_BUYER_ID_SERNO_LABEL_RE = re.compile(
    r"საიდენტიფიკაციო\s*/\s*პირადი\s*ნომერი|საიდენტიფიკაციო\s*/\s*პირადი",
    re.UNICODE | re.IGNORECASE,
)


def _find_buyer_id_serno_label_index(lines: list[str], buyer_label_idx: int) -> int | None:
    """First ``საიდენტიფიკაციო / პირადი ნომერი`` row after the buyer დასახელება caption."""
    lo = buyer_label_idx + 1
    hi = min(len(lines), buyer_label_idx + 40)
    for j in range(lo, hi):
        ln = lines[j]
        if _BUYER_ID_SERNO_LABEL_RE.search(ln):
            return j
        if "საიდენტიფიკაციო" in ln and "პირადი" in ln and "/" in ln:
            return j
    return None


# ``დასრუ*ლების`` — use Georgian ``უ`` (U+10E3), not ASCII ``u``. Tolerates OCR doubling ``უ``.
# RS.ge often OCRs spaces/glyphs between ``დასრულების`` and ``ადგილი``; endings vary
# (ადგილი / ადგილის / ადგილში). Optional ``ტრანსპორტირების`` prefix on same or merged line.
_COMPLETION_CAPTION_SHORT = re.compile(
    r"დასრუ*ლების\s*.{0,44}?ადგილ(?:ი|ის|ში|ზე)?(?:\s*\([^)]{0,40}\))?",
    re.UNICODE,
)
_COMPLETION_CAPTION_WITH_TRANSPORT = re.compile(
    r"ტრანსპორტირების\s*.{0,56}?დასრუ*ლების\s*.{0,44}?ადგილ(?:ი|ის|ში|ზე)?(?:\s*\([^)]{0,40}\))?",
    re.UNICODE,
)
_COMPLETION_TAIL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"ტრანსპორტირების\s*.{0,56}?დასრუ*ლების\s*.{0,44}?ადგილ(?:ი|ის|ში|ზე)?"
        r"(?:\s*\([^)]{0,40}\))?\s*[:\-–—]?\s*(.+)$",
        re.UNICODE,
    ),
    re.compile(
        r"დასრუ*ლების\s*.{0,44}?ადგილ(?:ი|ის|ში|ზე)?"
        r"(?:\s*\([^)]{0,40}\))?\s*[:\-–—]?\s*(.+)$",
        re.UNICODE,
    ),
)


def _line_is_transport_start_place_caption(line: str) -> bool:
    """``… დაწყების ადგილი`` — origin / seller side; not the buyer destination."""
    return "დაწყების" in line and "ადგილი" in line


def _looks_like_physical_address_text(s: str) -> bool:
    t = re.sub(r"\s+", " ", s.strip())
    if len(t) < 10:
        return False
    if re.search(r"ტრანსპორტირების\s*სახე", t):
        return False
    if _trim_physical_address_start(t):
        return True
    if any(c in t for c in _CITY_TOKENS):
        return True
    if any(h in t for h in _STREET_HINTS):
        return True
    return False


def _tail_after_completion_caption(chunk: str) -> str | None:
    for pat in _COMPLETION_TAIL_PATTERNS:
        m = pat.search(chunk)
        if not m:
            continue
        rest = m.group(1).strip()
        if len(rest) < 8:
            continue
        if _looks_like_physical_address_text(rest):
            return rest
    return None


def _chunk_has_completion_caption(chunk: str) -> bool:
    return bool(
        _COMPLETION_CAPTION_WITH_TRANSPORT.search(chunk)
        or _COMPLETION_CAPTION_SHORT.search(chunk)
    )


def _collect_completion_caption_spans(lines: list[str]) -> list[tuple[int, int]]:
    """
    Return (start_line, span_len) for each window where ``დასრულების ადგილი``
    appears (caption may span up to 4 OCR lines). Skips windows that are only
    ``დაწყების ადგილი`` without ``დასრულების``.
    """
    n = len(lines)
    spans: list[tuple[int, int]] = []
    for i in range(n):
        for span in (1, 2, 3, 4):
            if i + span > n:
                break
            chunk = " ".join(lines[i : i + span])
            if re.search(r"დაწყების\s*.{0,24}?ადგილ", chunk) and not _chunk_has_completion_caption(
                chunk
            ):
                continue
            if _chunk_has_completion_caption(chunk):
                spans.append((i, span))
    # Dedupe: same start line i may match several span lengths — keep the widest window.
    by_start: dict[int, int] = {}
    for i0, sp in spans:
        if i0 not in by_start or sp > by_start[i0]:
            by_start[i0] = sp
    return sorted(((i0, by_start[i0]) for i0 in by_start), key=lambda t: t[0])


def _extract_destination_address_after_completion(
    lines: list[str], buyer_label_line_idx: int | None
) -> str | None:
    """
    Buyer / receiver address on RS.ge: value tied to
    ``ტრანსპორტირების დასრულების ადგილი``, not the first address block
    (``დაწყების ადგილი`` / seller).
    """
    spans = _collect_completion_caption_spans(lines)
    if not spans:
        return None
    if buyer_label_line_idx is not None:
        after_buyer = [t for t in spans if t[0] >= buyer_label_line_idx]
        if after_buyer:
            spans = after_buyer
    # Drop windows whose *first* line is only ``დაწყების`` — merged (i,4) chunks can
    # include both rows; the completion row is where ``დასრულების`` starts.
    spans = [(i, s) for i, s in spans if "დასრულების" in lines[i]]
    if not spans:
        return None
    # First completion caption in reading order after the buyer block.
    i, span = spans[0]
    span = min(span, 2)
    n = len(lines)
    for extend in (0, 1, 2):
        piece = " ".join(lines[i : min(i + span + extend, n)])
        tail = _tail_after_completion_caption(piece)
        if tail:
            return tail
    # RS.ge column OCR often places the destination *above* ``დასრულების ადგილი``.
    for k in range(i - 1, max(-1, i - 20), -1):
        if k < 0:
            break
        cand = lines[k].strip()
        if not cand:
            continue
        if re.fullmatch(r"[\d\s/\-]{6,24}", cand):
            continue
        if cand in ("შინაარსი",) or len(cand) < 6:
            continue
        if re.match(r"^ოპერაციის\b", cand):
            continue
        if _line_is_transport_start_place_caption(cand):
            continue
        if _COMPLETION_CAPTION_SHORT.search(cand) or _COMPLETION_CAPTION_WITH_TRANSPORT.search(cand):
            continue
        trimmed = _trim_physical_address_start(cand)
        if trimmed:
            return trimmed
        if _looks_like_physical_address_text(cand):
            return cand
    start_scan = i + span
    for j in range(start_scan, min(start_scan + 18, n)):
        cand = lines[j].strip()
        if not cand:
            continue
        if re.fullmatch(r"[\d\s/\-]{6,24}", cand):
            continue
        if _line_is_transport_start_place_caption(cand):
            continue
        if re.match(r"^ოპერაციის\b", cand):
            continue
        if re.search(r"ტრანსპორტირების\s*სახე", cand):
            continue
        if _COMPLETION_CAPTION_SHORT.search(cand) and len(cand) < 120:
            continue
        trimmed = _trim_physical_address_start(cand)
        if trimmed:
            return trimmed
        if _looks_like_physical_address_text(cand):
            return cand
    return None


def _buyer_section_char_offset(full_text: str) -> int | None:
    m = re.search(
        r"მყიდველის\s*\([^)]*მიმღების[^)]*\)\s*დასახელება|მყიდველის",
        full_text,
        re.UNICODE,
    )
    return m.start() if m else None


def _extract_destination_address_fulltext_window(full_text: str) -> str | None:
    """
    When line-based merging misses a split caption, scan the raw string for
    completion captions and read the following physical-address line(s).
    """
    buyer_off = _buyer_section_char_offset(full_text)
    candidates: list[re.Match[str]] = []
    for rx in (_COMPLETION_CAPTION_WITH_TRANSPORT, _COMPLETION_CAPTION_SHORT):
        candidates.extend(list(rx.finditer(full_text)))
    if not candidates:
        return None
    candidates.sort(key=lambda m: m.start())
    if buyer_off is not None:
        scoped = [m for m in candidates if m.start() >= buyer_off - 80]
        if scoped:
            candidates = scoped
    for m in candidates:
        tail = full_text[m.end() : m.end() + 1200]
        if "სასაქონლო" in tail:
            tail = tail.split("სასაქონლო", 1)[0]
        for ln in _rs_source_lines(tail):
            if not ln.strip():
                continue
            if _line_is_transport_start_place_caption(ln):
                continue
            if _COMPLETION_CAPTION_SHORT.search(ln) and len(ln) < 120:
                continue
            if re.fullmatch(r"[\d\s/\-]{6,24}", ln.strip()):
                continue
            trimmed = _trim_physical_address_start(ln)
            if trimmed:
                return trimmed
            if _looks_like_physical_address_text(ln):
                return ln.strip()
    return None


def preview_rs_buyer_header_text(full_text: str, *, max_chars: int = 12000) -> str | None:
    """
    Raw-ish slice from the buyer caption through the product grid header — useful
    to verify OCR keywords (``ტრანსპორტირების დასრულების ადგილი``, etc.).
    """
    m = re.search(
        r"(მყიდველის[\s\S]{0,24000}?)სასაქონლო\s*ზედნადების\s*ცხრილი",
        full_text,
        re.UNICODE,
    )
    if not m:
        return None
    return m.group(1)[:max_chars]


def _buyer_address_line_after_id_label(lines: list[str], buyer_label_idx: int) -> str | None:
    """Physical address row after buyer ``საიდენტიფიკაციო / პირადი ნომერი`` (skip ID digits)."""
    j = _find_buyer_id_serno_label_index(lines, buyer_label_idx)
    if j is None:
        return None
    for off in (1, 2, 3):
        k = j + off
        if k >= len(lines):
            break
        cand = lines[k].strip()
        if not cand:
            continue
        if re.fullmatch(r"[\d\s]{6,15}", cand):
            continue
        return cand
    return None


def _extract_buyer_address_rs_line_order(full_text: str) -> str | None:
    lines = _rs_source_lines(full_text)
    bi = _find_buyer_dasakhleba_label_index(lines)
    dest = _extract_destination_address_after_completion(lines, bi)
    if not dest:
        dest = _extract_destination_address_fulltext_window(full_text)
    if dest:
        trimmed = _trim_physical_address_start(dest)
        return trimmed or dest
    if bi is None:
        return None
    raw_addr = _buyer_address_line_after_id_label(lines, bi)
    if not raw_addr:
        return None
    trimmed = _trim_physical_address_start(raw_addr)
    return trimmed or raw_addr


_HASH_CODE_IN_ADDRESS = re.compile(r"#\s*\d+", re.UNICODE)

_ORIGIN_CAPTION_RE = re.compile(
    r"ტრანსპორტირების\s*დაწყების\s*ადგილ",
    re.UNICODE,
)


def _extract_origin_address(raw_text: str) -> str | None:
    """
    Extract field 7: ტრანსპორტირების დაწყების ადგილი (origin/branch address).
    RS.ge OCR layout: the address value sits on the line ABOVE or SAME LINE as
    the caption (parallel columns). Strategy:
    1. Find the line containing დაწყების ადგილი caption.
    2. Check same line (text before the caption keyword).
    3. Check 1-3 lines ABOVE for a physical address or #NNN code.
    4. Fallback: scan all lines for #NNN near city tokens.
    """

    def _strip_left_col_labels(s: str) -> str:
        """Remove parallel-column label often glued before the physical address."""
        return re.sub(r"^ოპერაციის\s+", "", s.strip()).strip()

    lines = _rs_source_lines(raw_text)
    for i, ln in enumerate(lines):
        if not _ORIGIN_CAPTION_RE.search(ln):
            continue
        # --- same line: text before the caption keyword ---
        m = _ORIGIN_CAPTION_RE.search(ln)
        before = ln[: m.start()].strip() if m else ""
        before = re.sub(r"^[\|\d\s]+", "", before).strip()
        before = _strip_left_col_labels(before)
        if len(before) > 5 and (
            _HASH_CODE_IN_ADDRESS.search(before)
            or any(c in before for c in _CITY_TOKENS)
            or any(h in before for h in _STREET_HINTS)
        ):
            return before
        # --- lines above (up to 4) ---
        for k in range(i - 1, max(-1, i - 5), -1):
            cand = lines[k].strip()
            if not cand or len(cand) < 5:
                continue
            # skip pure caption/label lines
            if re.search(
                r"დასახელება|საიდენტიფიკაციო|გამყიდველ|ოპერაციის\s*შინაარს",
                cand,
            ):
                # but if it ALSO has address content, extract just that part
                addr_m = _HASH_CODE_IN_ADDRESS.search(cand)
                if addr_m:
                    # grab from city token or # onward
                    for tok in list(_CITY_TOKENS) + ["#"]:
                        p = cand.find(tok)
                        if p != -1:
                            return cand[p:].strip()
                continue
            if re.fullmatch(r"[\d\s/\-|]+", cand):
                continue
            if _HASH_CODE_IN_ADDRESS.search(cand):
                return _strip_left_col_labels(cand)
            trimmed = _trim_physical_address_start(cand)
            if trimmed:
                return _strip_left_col_labels(trimmed)
            if any(c in cand for c in _CITY_TOKENS):
                return _strip_left_col_labels(cand)
        break
    # --- global fallback: find #NNN near city name ---
    for ln in lines:
        if _HASH_CODE_IN_ADDRESS.search(ln) and any(c in ln for c in _CITY_TOKENS):
            # strip noise prefixes (table pipes / digits / operation column label)
            cleaned = re.sub(r"^[\|\d\s,/\-]+", "", ln).strip()
            cleaned = _strip_left_col_labels(cleaned)
            if cleaned:
                return cleaned
    return None


_IS_RETURN_OPERATION_RE = re.compile(
    r"უკან\s*დაბრუნება|საკრედიტო|კორექტირება",
    re.UNICODE,
)
_SUPPLIER_HQ_FRAGMENTS = (
    "თ.ერისთავის",
    "ერისთავის_1",
    "200249043",
)


def _is_supplier_hq_address(addr: str) -> bool:
    """Return True if this address is the seller/supplier HQ, not a store."""
    if not addr:
        return False
    return any(frag in addr for frag in _SUPPLIER_HQ_FRAGMENTS)


def _extract_store_branch_address(raw_text: str) -> str | None:
    """
    Extract the store/branch address from RS.ge waybill.

    - Return invoices (უკან დაბრუნება): store is in field 7 (origin).
    - Delivery invoices (ქვე-ზედნადები / normal): store is in field 8 (destination).

    Skips supplier HQ addresses (თ.ერისთავის / ერისთავის_1).
    """
    is_return = bool(_IS_RETURN_OPERATION_RE.search(raw_text))

    origin = _extract_origin_address(raw_text)
    destination = _extract_buyer_address_rs_line_order(raw_text)

    if is_return:
        if origin and not _is_supplier_hq_address(origin):
            return origin
        if destination and not _is_supplier_hq_address(destination):
            return destination
    else:
        if destination and not _is_supplier_hq_address(destination):
            return destination
        if origin and not _is_supplier_hq_address(origin):
            return origin
    return None


# ---------------------------------------------------------------------------
# Store name: pdfplumber bbox fallback (digital PDFs)
# ---------------------------------------------------------------------------

_STORE_HEADER_JUNK = re.compile(
    r"(სასაქონლო\s*ზედნადები|ზედნადები\s*#|ელ[-\s]*\d{5,})",
    re.UNICODE | re.IGNORECASE,
)

# Small instructional / field labels (often under the box) — not the legal entity name.
_STORE_NAME_JUNK_LINE = re.compile(
    r"(^|\s)(გვარი|სახელი|წომერი|ღომერი|ნომერი|მიმღები|"
    r"ან\s+სახელი\s+და\s+გვარი|და\s+გვარი|საიდენტიფიკაციო|პირადი\s*ნომერი)($|\s)",
    re.UNICODE | re.IGNORECASE,
)

_STORE_NEGATIVE_HINTS = (
    "გამყიდველ",
    "გამგზავნ",
    "საიდენტიფიკაციო",
    "პირადი ნომერი",
    "ზედნადები",
    "თარიღი",
    "დრო",
)


def _is_column_header_noise(line: str) -> bool:
    """Table column titles like 'გვარი / ნომერი' repeated by OCR."""
    t = re.sub(r"\s+", " ", line.strip())
    if not t:
        return True
    if "შპს" in t or "სს " in t or t.startswith("სს "):
        return False
    if t.count("გვარი") >= 2 or t.count("ნომერი") >= 2:
        return True
    if re.search(r"გვარი.*ნომერი|ნომერი.*გვარი", t) and len(t) < 90:
        return True
    return False


def _looks_like_legal_entity_line(line: str) -> bool:
    s = line.strip()
    if len(s) < 4:
        return False
    if _is_column_header_noise(s):
        return False
    if re.fullmatch(r"\d[\d\s,/\-]*", s):
        return False
    if _STORE_HEADER_JUNK.search(s) and "შპს" not in s and "სს " not in s and not s.startswith(
        "სს "
    ):
        return False
    if "შპს" in s or "სს " in s or s.startswith("სს "):
        return True
    if "ოპერაციის" in s.casefold() or "ტრანსპორტირების" in s.casefold():
        return False
    if re.search(r"თბილისი\s*,|ბათუმი\s*,|ქუთაისი\s*,", s) and "#" in s and "შპს" not in s:
        return False
    if re.search(r"თანხა|ლარებში|თეთრი", s) and "შპს" not in s and "სს " not in s:
        return False
    if len(re.sub(r"[^\u10a0-\u10ff]", "", s)) >= 12:
        return True
    return False


def _is_store_name_junk_line(line: str) -> bool:
    t = re.sub(r"\s+", " ", line.strip())
    if not t:
        return True
    if _STORE_HEADER_JUNK.search(t) and not _looks_like_legal_entity_line(t):
        return True
    if _STORE_NAME_JUNK_LINE.search(t) and not _looks_like_legal_entity_line(t):
        return True
    # OCR garble common on form footers
    if re.search(r"გვარი\s+წომერი|გვარი\s+და\s+სახელი", t, re.UNICODE):
        return not _looks_like_legal_entity_line(t)
    return False


def _word_center(w: dict[str, Any]) -> tuple[float, float]:
    return ((float(w["x0"]) + float(w["x1"])) / 2, (float(w["top"]) + float(w["bottom"])) / 2)


def _cluster_words_into_lines(
    words: list[dict[str, Any]], y_tol: float = 3.0
) -> list[list[dict[str, Any]]]:
    if not words:
        return []
    sorted_w = sorted(words, key=lambda w: (float(w["top"]), float(w["x0"])))
    lines: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    last_key: float | None = None
    for w in sorted_w:
        mid_y = (float(w["top"]) + float(w["bottom"])) / 2
        key = round(mid_y / y_tol) * y_tol
        if last_key is None or abs(key - last_key) <= y_tol:
            current.append(w)
        else:
            if current:
                lines.append(current)
            current = [w]
        last_key = key
    if current:
        lines.append(current)
    for line in lines:
        line.sort(key=lambda w: float(w["x0"]))
    return lines


def _line_text(line: list[dict[str, Any]]) -> str:
    return " ".join(str(w.get("text") or "") for w in line).strip()


def _score_store_candidate(line: str) -> float:
    if len(line) < 4:
        return -100.0
    low = line.lower()
    score = 0.0
    if any(x in line for x in ("შპს", "სს ", "სს\t", "სს\n")):
        score += 4.0
    if re.search(r"[ა-ჰ]{6,}", line):
        score += 2.0
    if any(h in low for h in _STORE_NEGATIVE_HINTS):
        score -= 6.0
    if re.fullmatch(r"\d+", line.strip()):
        score -= 8.0
    if "დასახელება" in low and "მყიდველ" in low:
        score -= 5.0
    if _STORE_HEADER_JUNK.search(line):
        score -= 10.0
    score += min(len(line), 80) / 80.0
    return score


def _extract_store_name_from_buyer_bbox(
    words: list[dict[str, Any]], page_w: float, page_h: float
) -> str | None:
    """
    RS.ge: buyer legal name sits left of buyer საიდენტიფიკაციო, under the
    ``მყიდველი (მიმღები)`` label — narrow horizontal band between those anchors.
    """
    if not words or page_w <= 0 or page_h <= 0:
        return None

    label_words = [
        w
        for w in words
        if (
            "მყიდველ" in (w.get("text") or "")
            or "მიმღებ" in (w.get("text") or "")
        )
        and float(w["x0"]) < page_w * 0.72
        and float(w["top"]) < page_h * 0.58
    ]
    if not label_words:
        return None
    y_l_top = min(float(w["top"]) for w in label_words)
    y_l_bot = max(float(w["bottom"]) for w in label_words)

    id_words = [
        w
        for w in words
        if "საიდენტიფიკაციო" in (w.get("text") or "")
        and float(w["top"]) > y_l_top - 20
        and float(w["top"]) < page_h * 0.55
        and float(w["x0"]) > page_w * 0.22
    ]
    y_id_top = min(float(w["top"]) for w in id_words) if id_words else min(
        y_l_bot + 110, page_h * 0.48
    )

    x_lo, x_hi = page_w * 0.02, page_w * 0.52
    # One–two lines under the buyer caption (company name row); avoid address boxes below.
    y_lo = max(0.0, y_l_bot + 0.5)
    y_hi = min(page_h * 0.42, y_l_bot + 56.0, y_id_top - 1.0)
    if y_hi <= y_lo:
        y_hi = min(page_h * 0.45, y_l_bot + 72.0)

    band: list[dict[str, Any]] = []
    for w in words:
        cx, cy = _word_center(w)
        if not (x_lo <= cx <= x_hi and y_lo <= cy <= y_hi):
            continue
        tx = (w.get("text") or "").strip()
        if not tx or len(tx) < 2:
            continue
        if "საიდენტიფიკაციო" in tx or "პირადი" in tx:
            continue
        if "მყიდველის" in tx and "დასახელება" in tx:
            continue
        if tx.isdigit() and len(tx) >= 9:
            continue
        band.append(w)

    if not band:
        return None

    best_line: str | None = None
    best_score = -1e9
    for line in _cluster_words_into_lines(band):
        lt = _line_text(line)
        if _is_transport_or_seller_glue(lt):
            continue
        if _is_store_name_junk_line(lt):
            continue
        sc = _score_store_candidate(lt)
        if sc > best_score:
            best_score = sc
            best_line = lt
    if best_line and best_score >= 0.5:
        return _isolate_buyer_store_name_from_line(best_line.strip())
    return None


def _extract_store_name_from_layout(
    words: list[dict[str, Any]], page_w: float, page_h: float
) -> str | None:
    """Layout fallback: buyer bbox only (no invoice-header sweep)."""
    return _extract_store_name_from_buyer_bbox(words, page_w, page_h)


def _extract_store_name(
    text: str,
    first_page_words: list[dict[str, Any]],
    page_w: float,
    page_h: float,
) -> str | None:
    lines = _rs_source_lines(text)
    direct = _store_name_line_above_buyer_dasakhleba(lines)
    if direct:
        return direct
    adj = _store_name_buyer_adjacent_scan(lines)
    if adj:
        return adj
    layout = _extract_store_name_from_layout(first_page_words, page_w, page_h)
    if layout:
        return layout
    return _extract_store_name_pre_table_keyword(lines)


# ---------------------------------------------------------------------------
# Cleaning & DB fuzzy match
# ---------------------------------------------------------------------------

_SN_INLINE = re.compile(
    r"(?:საიდენტიფიკაციო|პირადი\s*ნომერი)\s*[:]?\s*\d{5,15}",
    re.UNICODE | re.IGNORECASE,
)
_TRAILING_IDENT = re.compile(
    r"(?:\s+|[,;|])+(\d{9,12})(?:\s*$)",
    re.UNICODE,
)
_LEADING_IDENT = re.compile(r"^(\d{9,12})(?:\s+|\s*[,;|-]\s*)", re.UNICODE)
_ROW_NUM_PREFIX = re.compile(r"^#?\s*\d{1,3}[.)\s]+", re.UNICODE)
_TRAILING_PAREN_JUNK = re.compile(r"\s*\([^)]{1,30}\)\s*$", re.UNICODE)
_SHPS_SPACED = re.compile(r"შ\s*პ\s*ს", re.UNICODE)
_MULTI_SPACE = re.compile(r"\s+")

# ---------------------------------------------------------------------------
# Georgian OCR fixes (common confusions: წ vs ნ, missing უ, ლ vs ნ)
# Applied to cleaned store names and buyer addresses before fuzzy DB match.
# ---------------------------------------------------------------------------

# Whole-phrase fixes for known legal names (longer / genitive before shorter).
# Use regex only (no naive ``str.replace``) so ``შპს ორი წაბიჯი`` does not
# become ``შპს შპს ორი ნაბიჯი``.
_STORE_NAME_OCR_PHRASE_FIXES: list[tuple[re.Pattern[str], str]] = [
    # ``ნაბიჯი`` misread as ``წაბიჯი`` (წ vs ნ).
    (
        re.compile(r"(?:შპს\s+)?ორი\s+წაბიჯის", re.UNICODE),
        "შპს ორი ნაბიჯის",
    ),
    (
        re.compile(r"(?:შპს\s+)?ორი\s+წაბიჯი", re.UNICODE),
        "შპს ორი ნაბიჯი",
    ),
    # Doubled legal prefix / extra space after შპს.
    (re.compile(r"შპსშპს", re.UNICODE), "შპს"),
    (re.compile(r"შპს\s{2,}", re.UNICODE), "შპს "),
    # შპს glued to the next word (missing space).
    (
        re.compile(r"შპს(?=[\u10D0-\u10FF])", re.UNICODE),
        "შპს ",
    ),
    # სს glued to name (e.g. სსზღ… → სს ზღ…).
    (
        re.compile(r"სს(?=[\u10D0-\u10FF])", re.UNICODE),
        "სს ",
    ),
    # Digit 0 misread as ო inside numeric runs (IDs / table noise in name cell).
    (re.compile(r"(?<=\d)ო(?=\d)", re.UNICODE), "0"),
    (re.compile(r"(?<=\d)ო(?=\s|$)", re.UNICODE), "0"),
    (re.compile(r"(?<![\u10D0-\u10FF])ო(?=\d)", re.UNICODE), "0"),
    # Common letter confusions in short legal-name tokens (ლ↔ნ, წ↔ნ).
    (re.compile(r"\bწპს\b", re.UNICODE), "შპს"),
    (re.compile(r"\bშპწ\b", re.UNICODE), "შპს"),
    (re.compile(r"\bშპნ\b", re.UNICODE), "შპს"),
    (re.compile(r"([ა-ჰ])\1{2,}", re.UNICODE), r"\1\1"),
]

_ADDRESS_OCR_PHRASE_FIXES: list[tuple[re.Pattern[str], str]] = [
    # წინუბანი: leading წ misread as ნ; dropped უ.
    (re.compile(r"ნინუბანი", re.UNICODE), "წინუბანი"),
    (re.compile(r"ნენუბანი", re.UNICODE), "წინუბანი"),
    (re.compile(r"წინბანი", re.UNICODE), "წინუბანი"),
    (re.compile(r"წინუბნი", re.UNICODE), "წინუბანი"),
    # დიდი ლილო (Tbilisi area): ლ/ნ confusion or wrong middle vowel.
    (re.compile(r"დიდი\s+ნილო", re.UNICODE), "დიდი ლილო"),
    (re.compile(r"დიდი\s+ნინო", re.UNICODE), "დიდი ლილო"),
    (re.compile(r"დიდი\s+ლინო", re.UNICODE), "დიდი ლილო"),
    # გლდანი (district / street label variants).
    (re.compile(r"გელდანი", re.UNICODE), "გლდანი"),
    (re.compile(r"გლდნი", re.UNICODE), "გლდანი"),
    (re.compile(r"გზდანი", re.UNICODE), "გლდანი"),
    # ვარკეთილი.
    (re.compile(r"ვარკეტილი", re.UNICODE), "ვარკეთილი"),
    (re.compile(r"ვარკთილი", re.UNICODE), "ვარკეთილი"),
    (re.compile(r"ვარკეთილში", re.UNICODE), "ვარკეთილი"),
    # ისანი / სამგორი.
    (re.compile(r"\bისნი\b", re.UNICODE), "ისანი"),
    (re.compile(r"სამგორში", re.UNICODE), "სამგორი"),
    (re.compile(r"სამგორს", re.UNICODE), "სამგორი"),
    # ნუცუბიძე (უ dropout, ძ↔ჯ).
    (re.compile(r"ნუცბიძე", re.UNICODE), "ნუცუბიძე"),
    (re.compile(r"ნუცუბიჯე", re.UNICODE), "ნუცუბიძე"),
    (re.compile(r"ნუცუბიძის\s+გამზ", re.UNICODE), "ნუცუბიძის გამზ"),
]


def _apply_ocr_corrections_store_name(s: str) -> str:
    if not s:
        return s
    t = re.sub(r"\s+", " ", s.strip())
    for pat, repl in _STORE_NAME_OCR_PHRASE_FIXES:
        t = pat.sub(repl, t)
    return _MULTI_SPACE.sub(" ", t).strip()


def _apply_ocr_corrections_address(addr: str | None) -> str | None:
    if not addr:
        return addr
    t = addr.replace("\u00a0", " ")
    t = re.sub(r"\s+", " ", t.strip())
    for pat, repl in _ADDRESS_OCR_PHRASE_FIXES:
        t = pat.sub(repl, t)
    return _MULTI_SPACE.sub(" ", t).strip() or None


def clean_store_name(name: str | None) -> str | None:
    """
    Strip საიდენტიფიკაციო / personal number snippets and standalone ID tokens
    often merged with legal names in PDF table cells.

    Also drops common LT Distribution / seller fragments that leak into the
    buyer name field after OCR.

    Finally applies a small set of known OCR phrase fixes (e.g. ``ორი წაბიჯი``
    → ``შპს ორი ნაბიჯი``) so fuzzy matching and unknown-buyer reprocessing see
    canonical names.
    """
    if not name:
        return None
    s = name.replace("\u00a0", " ").strip()
    s = _ROW_NUM_PREFIX.sub("", s)
    s = _SHPS_SPACED.sub("შპს", s)
    s = _SN_INLINE.sub("", s)
    s = _TRAILING_IDENT.sub("", s)
    s = _LEADING_IDENT.sub("", s)
    s = _SELLER_NAME_NOISE.sub(" ", s)
    s = _MULTI_SPACE.sub(" ", s).strip(" ,;|-")
    s = _apply_ocr_corrections_store_name(s)
    if re.search(r"(?:შპს|სს)", s):
        s = _TRAILING_PAREN_JUNK.sub("", s).strip(" ,;|-")
    return s or None


def _token_overlap_score(a: str, b: str) -> float:
    """Jaccard overlap on whitespace tokens (helps short legal names)."""
    wa = {w for w in a.casefold().split() if w}
    wb = {w for w in b.casefold().split() if w}
    if not wa or not wb:
        return 0.0
    inter = len(wa & wb)
    union = len(wa | wb)
    return inter / union if union else 0.0


def _fuzzy_match_store(
    name: str | None, db_path: Path | None, threshold: float
) -> tuple[int | None, str | None, float]:
    if not name or not db_path:
        return None, None, 0.0
    try:
        conn = sqlite3.connect(db_path)
    except sqlite3.Error:
        return None, None, 0.0
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM stores")
        rows = cur.fetchall()
    finally:
        conn.close()
    if not rows:
        return None, None, 0.0

    best_id: int | None = None
    best_name: str | None = None
    best_ratio = 0.0
    key = name.casefold()
    for sid, sname in rows:
        if sname is None:
            continue
        db_key = str(sname).casefold()
        sm = difflib.SequenceMatcher(None, key, db_key)
        char_ratio = max(sm.ratio(), sm.quick_ratio())
        tok = _token_overlap_score(name, str(sname))
        r = max(char_ratio, tok * 0.9)
        if r > best_ratio:
            best_ratio = r
            best_id = int(sid)
            best_name = str(sname)
    if best_ratio >= threshold and best_id is not None:
        return best_id, best_name, best_ratio
    return None, None, best_ratio


# ---------------------------------------------------------------------------
# Buyer block → addresses (cities / street vocabulary)
# ---------------------------------------------------------------------------

_BUYER_BLOCK_PATTERNS = (
    re.compile(
        r"მყიდველის\s*(?:\([^)]*\))?\s*დასახელება[^\n]*\n([\s\S]{0,4000}?)"
        r"(?=ტრანსპორტირების\s*დაწყების|ოპერაციის\s*შინაარსი|სასაქონლო\s*ზედნადების\s*ცხრილი|"
        r"მიწოდებული\s*საქონლის)",
        re.UNICODE,
    ),
    re.compile(
        r"ჩამბარებ(?:ელი|ლის)[^\n]*\n([\s\S]{0,2000}?)(?=ტრანსპორტირების|ოპერაციის|სასაქონლო)",
        re.UNICODE,
    ),
)

_CITY_TOKENS = (
    "თბილისი",
    "ქ.თბილისი",
    "ბათუმი",
    "ქუთაისი",
    "რუსთავი",
    "ზუგდიდი",
    "ფოთი",
    "გორი",
    "სამტრედია",
    "ხაშური",
    "მცხეთა",
    "ჭიათურა",
    "ზესტაფონი",
    "სენაკი",
    "მარნეული",
    "თელავი",
    "Tbilisi",
    "Batumi",
    "Kutaisi",
    "Rustavi",
    "Zugdidi",
    "Poti",
    "Gori",
)

_STREET_HINTS = (
    "ქ.",
    "ქუჩა",
    "გამზირი",
    "გზატკეცილი",
    "ხეივანი",
    "მიკრორაიონი",
    "გზა",
    "მოპირდ",
    "სოფელი",
    "ერისთავის",
)

_ADDRESS_PHYSICAL_START = re.compile(
    r"(თბილისი|ქ\.თბილისი|ბათუმი|ქუთაისი|რუსთავი|ზუგდიდი|ფოთი|გორი|"
    r"სამტრედია|ხაშური|მცხეთა|ჭიათურა|ზესტაფონი|სენაკი|მარნეული|თელავი|"
    r"Tbilisi|Batumi|Kutaisi|Rustavi|Zugdidi|Poti|Gori|"
    r"სოფელი|სოფ\.|"
    r"ქ\.\s*(?:თბილისი|[\u10a0-\u10ff]{2,})|ქუჩა|გამზირი|გზატკეცილი)",
    re.UNICODE | re.IGNORECASE,
)


def _trim_physical_address_start(line: str) -> str | None:
    """
    Drop leading administrative phrases; keep text from a city name or
    street prefix (ქ., ქუჩა, გამზირი, …) onward.
    """
    t = re.sub(r"\s+", " ", line.strip())
    if not t:
        return None
    if re.match(
        r"^(ოპერაციის|ტიპი|მიზანი|ტრანსპორტირების)",
        t,
        re.UNICODE,
    ):
        m = _ADDRESS_PHYSICAL_START.search(t)
        return t[m.start() :].strip() if m else None
    m = _ADDRESS_PHYSICAL_START.search(t)
    if m:
        return t[m.start() :].strip()
    for hint in ("ქ.", "ქუჩა", "გამზირი", "გზატკეცილი", "სოფელი"):
        p = t.find(hint)
        if p != -1:
            return t[p:].strip()
    return None


def _extract_buyer_block_text(full_text: str) -> str | None:
    for pat in _BUYER_BLOCK_PATTERNS:
        m = pat.search(full_text)
        if m:
            return m.group(1).strip()
    return None


def _extract_header_before_line_items(full_text: str) -> str | None:
    """Region from buyer section through transport boxes (before product grid)."""
    m = re.search(
        r"მყიდველის([\s\S]{0,12000}?)სასაქონლო\s*ზედნადების\s*ცხრილი",
        full_text,
        re.UNICODE,
    )
    return m.group(1).strip() if m else None


def _extract_buyer_addresses(block: str | None) -> str | None:
    if not block:
        return None
    work = block
    m = _COMPLETION_CAPTION_WITH_TRANSPORT.search(work) or _COMPLETION_CAPTION_SHORT.search(work)
    if m:
        tail = work[m.end() :]
        tail = re.sub(r"^[:\s\-–—]+", "", tail, count=1)
        if tail.strip():
            work = tail
    hits: list[str] = []
    for raw in work.splitlines():
        line = raw.strip()
        if len(line) < 4:
            continue
        trimmed = _trim_physical_address_start(line)
        if not trimmed:
            continue
        if any(c in trimmed for c in _CITY_TOKENS):
            hits.append(trimmed)
            continue
        if any(s in trimmed for s in _STREET_HINTS):
            hits.append(trimmed)
            continue
    if not hits:
        return None
    # De-duplicate while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return " | ".join(out)


# ---------------------------------------------------------------------------
# Waybill, date, time
# ---------------------------------------------------------------------------

_WAYBILL_PATTERNS = (
    # Appendix (დანართი): waybill digits alone at line start, then ``სასაქონლო ზედნადებ...``.
    re.compile(
        r"(?:^|\n)(\d{8,14}(?:/\d+)?)\s+სასაქონლო\s+ზედნადებ",
        re.UNICODE,
    ),
    re.compile(
        r"ელ[-\s]*([0-9]{6,}\s*/\s*[0-9]+|[0-9]{8,})",
        re.UNICODE | re.IGNORECASE,
    ),
    re.compile(
        r"(?:სასაქონლო\s*)?ზედნადები\s*#?\s*[:]?\s*(?:ელ[-\s]*)?([A-Za-z0-9\-\/\.]+)",
        re.UNICODE | re.IGNORECASE,
    ),
    re.compile(
        r"(?:ზედნადები|ზედნადების\s*№|Waybill)\s*[:#]?\s*([A-Za-z0-9\-\/\.]+)",
        re.UNICODE | re.IGNORECASE,
    ),
    re.compile(r"(?:№|#|No\.?)\s*[:#]?\s*([A-Z]{1,3}[\-/]?\d{4,})", re.UNICODE),
)


def _extract_waybill(text: str) -> str | None:
    for pat in _WAYBILL_PATTERNS:
        m = pat.search(text)
        if m:
            val = re.sub(r"\s+", "", m.group(1).strip())
            if val:
                return val
    return _extract_waybill_appendix_leading_digits(text)


def _extract_waybill_appendix_leading_digits(text: str) -> str | None:
    """
    When the usual labels are missing or garbled, appendix pages often still
    begin with the waybill token then ``დანართი`` / ``ზედნადებ`` within the same block.
    """
    head = (text or "").lstrip()[:500]
    m = re.match(r"^(\d{8,14}(?:/\d+)?)\s+", head)
    if not m:
        return None
    tail = head[m.start() : m.start() + min(len(head), 220)]
    if re.search(r"დანართი|ზედნადებ|სასაქონლო", tail, re.UNICODE):
        return re.sub(r"\s+", "", m.group(1).strip())
    return None


_DATE_UNDER_LABEL = re.compile(
    r"თარიღი\s*(?:\([^)]*\))?\s*[:#]?\s*(\d{1,2}[\/\.\-]\d{1,2}[\/\.\-]\d{2,4})",
    re.UNICODE,
)
_DATE_FALLBACK = (
    re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b"),
    re.compile(r"\b(\d{1,2}[\/\.\-]\d{1,2}[\/\.\-]\d{2,4})\b"),
)


def _extract_date_preferred(text: str) -> str | None:
    m = _DATE_UNDER_LABEL.search(text)
    if m:
        return m.group(1).strip()
    for pat in _DATE_FALLBACK:
        m2 = pat.search(text)
        if m2:
            return m2.group(1).strip()
    return None


_TIME_PATTERN = re.compile(
    r"\b(?:[01]?\d|2[0-3]):[0-5]\d:[0-5]\d\b",
)
_TIME_UNDER_LABEL = re.compile(
    r"დრო\s*(?:\([^)]*\))?\s*[:#]?\s*((?:[01]?\d|2[0-3]):[0-5]\d:[0-5]\d)",
    re.UNICODE,
)


def _extract_invoice_time(text: str, date_token: str | None) -> str | None:
    """Full ``HH:MM:SS`` near ``დრო`` label or after document date in header."""
    head = text
    cut = re.search(r"სასაქონლო\s*ზედნადების\s*ცხრილი", text, re.UNICODE)
    if cut:
        head = text[: cut.start()]
    m_label = _TIME_UNDER_LABEL.search(head)
    if m_label:
        return m_label.group(1)

    slice_ = head
    if date_token:
        idx = slice_.find(date_token)
        if idx != -1:
            slice_ = slice_[max(0, idx - 160) : idx + 520]
    m = _TIME_PATTERN.search(slice_)
    if m:
        return m.group(0)
    m2 = _TIME_PATTERN.search(head)
    return m2.group(0) if m2 else None


# ---------------------------------------------------------------------------
# Product tables
# ---------------------------------------------------------------------------

_NAME_KEYS = (
    "საქონლის დასახელება",
    "დასახელება",
    "სახელი",
    "ნივთი",
    "პროდუქტ",
    "name",
    "product",
    "item",
)
_QTY_KEYS = (
    "საქონლის რაოდენობა",
    "რაოდენობა",
    "რ-ბა",
    "რაოდ",
    "qty",
    "quantity",
    "აღრიცხვა",
)
_GENERIC_PRICE_KEYS = (
    "ფასი",
    "price",
    "amount",
)


def _normalize_cell(cell: str | None) -> str:
    if cell is None:
        return ""
    return re.sub(r"\s+", " ", str(cell)).strip()


def _cell_matches(cell: str, keys: tuple[str, ...]) -> bool:
    c = cell.lower()
    return any(k.lower() in c for k in keys)


def _parse_money_or_number(s: str) -> str:
    s = s.replace(" ", "").replace("\u00a0", "")
    s = s.replace(",", ".")
    return s.strip()


def _pick_price_column(headers_lower: list[str]) -> int | None:
    """Prefer unit-price column (ერთეული) over line total (საქონლის ფასი)."""
    for j, h in enumerate(headers_lower):
        if "ერთეულ" in h and "ფას" in h:
            return j
    for j, h in enumerate(headers_lower):
        if "საქონლის" in h and "ფას" in h and "ერთეულ" not in h:
            return j
    for j, h in enumerate(headers_lower):
        if _cell_matches(h, _GENERIC_PRICE_KEYS):
            return j
    return None


def _map_table_columns(header_row: list[str | None]) -> dict[str, int] | None:
    headers = [_normalize_cell(h).lower() for h in header_row]
    idx_name = idx_qty = None
    idx_price = None
    for j, h in enumerate(headers):
        if not h:
            continue
        if idx_name is None and _cell_matches(h, _NAME_KEYS):
            idx_name = j
        if idx_qty is None and _cell_matches(h, _QTY_KEYS):
            idx_qty = j
    hdr_raw = [_normalize_cell(header_row[k]) for k in range(len(header_row))]
    idx_price = _pick_price_column([x.lower() for x in hdr_raw])

    if idx_name is None or idx_qty is None or idx_price is None:
        return None
    return {"name": idx_name, "qty": idx_qty, "price": idx_price}


def _products_from_tables(tables: list[list[list[str | None]]]) -> list[ProductRow]:
    out: list[ProductRow] = []
    for table in tables:
        if not table or len(table) < 2:
            continue
        colmap = _map_table_columns(table[0])
        start_row = 1
        if colmap is None and len(table) > 1:
            colmap = _map_table_columns(table[1])
            start_row = 2
        if colmap is None:
            if len(table[0]) >= 3:
                colmap = {"name": 0, "qty": 1, "price": len(table[0]) - 1}
                start_row = 1
            else:
                continue
        max_idx = max(colmap.values())
        for row in table[start_row:]:
            if not row or len(row) <= max_idx:
                continue
            name = _normalize_cell(row[colmap["name"]])
            qty = _normalize_cell(row[colmap["qty"]])
            price = _normalize_cell(row[colmap["price"]])
            if not name and not qty and not price:
                continue
            if name.lower() in ("სულ", "total", "ჯამი"):
                continue
            out.append(
                ProductRow(
                    name=name,
                    quantity=_parse_money_or_number(qty) if qty else "",
                    price=_parse_money_or_number(price) if price else "",
                )
            )
    return out


_LINE_ITEM_PATTERN = re.compile(
    r"^(.+?)\s+(\d+(?:[.,]\d+)?)\s+(\d+(?:[.,]\d+)?)\s*$",
    re.UNICODE,
)


def _products_from_text_lines(text: str) -> list[ProductRow]:
    rows: list[ProductRow] = []
    for line in text.splitlines():
        line = line.strip()
        if len(line) < 5:
            continue
        m = _LINE_ITEM_PATTERN.match(line)
        if not m:
            continue
        name, qty, price = m.group(1).strip(), m.group(2), m.group(3)
        if _cell_matches(name.lower(), _NAME_KEYS) or name.lower() in ("სულ", "total"):
            continue
        rows.append(
            ProductRow(
                name=name,
                quantity=_parse_money_or_number(qty),
                price=_parse_money_or_number(price),
            )
        )
    return rows


_OCR_DECIMALS = re.compile(r"\d+\.\d{2,4}")


def _parse_tail_after_barcode(tail: str) -> tuple[str, str] | None:
    """
    After the 13-digit code: optional unit (ცალი), then qty / unit price / line total.
    Returns (quantity, unit_price).
    """
    t = re.sub(r"\s+", " ", tail.strip())
    t = re.sub(r"^ცალი\s+", "", t, flags=re.UNICODE)
    decs = _OCR_DECIMALS.findall(t)
    if len(decs) >= 3:
        return decs[0], decs[1]
    if len(decs) == 2:
        return decs[0], decs[1]
    if len(decs) == 1:
        return decs[0], ""
    return None


def _products_from_bundled_ocr_lines(text: str) -> list[ProductRow]:
    """
    RS.ge-style OCR lines: product text, 13-digit barcode, then decimals (qty, prices).
    """
    rows: list[ProductRow] = []
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw.strip())
        if len(line) < 25:
            continue
        low = line.casefold()
        if "საქონლის დასახელება" in line or "ზომის ერთეული" in line:
            continue
        if not re.search(r"\d{13}", line):
            continue
        m = re.search(r"(.+?)\s+(\d{13})\s+(.+)$", line)
        if not m:
            continue
        name = m.group(1).strip()
        name = re.sub(r"^#?\s*\d{1,3}\s+", "", name).strip()
        tail = m.group(3)
        if len(name) < 2:
            continue
        if _cell_matches(name.lower(), _NAME_KEYS) or name.lower() in ("სულ", "total", "#"):
            continue
        parsed = _parse_tail_after_barcode(tail)
        if not parsed:
            continue
        qty, unit_p = parsed
        rows.append(
            ProductRow(
                name=name,
                quantity=_parse_money_or_number(qty),
                price=_parse_money_or_number(unit_p) if unit_p else "",
            )
        )
    return rows


__all__ = [
    "PdfProcessResult",
    "ProductRow",
    "clean_store_name",
    "process_pdf",
]

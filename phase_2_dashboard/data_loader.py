"""
Read-only SQLite access for the Phase 2 dashboard.

All SQL lives here so ``app.py`` stays presentation-only and we can plug in
``ai_recommendations`` (or similar) later without touching query logic.
"""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import sys
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Paths & connection
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "amiko_v3.db"

_SQL_LINE_ITEMS_SELECT = """
SELECT
    ii.id AS line_id,
    ii.invoice_id,
    ii.product_id,
    COALESCE(p.name, ii.description, '') AS product_label,
    ii.quantity AS quantity,
    ii.unit_price AS unit_price,
    ii.line_total AS line_total
{extra_cols}
FROM invoice_items ii
LEFT JOIN products p ON p.id = ii.product_id
JOIN invoices i ON i.id = ii.invoice_id
"""


def resolve_db_path(explicit: Path | str | None = None) -> Path:
    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    return DEFAULT_DB_PATH.resolve()


def connect_readonly(db_path: Path | None = None) -> sqlite3.Connection:
    """Open SQLite in read-only URI mode (no writes even by accident)."""
    path = resolve_db_path(db_path)
    if not path.is_file():
        raise FileNotFoundError(f"Database not found: {path}")
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Date parsing (invoice_date is free-text from OCR / PDFs)
# ---------------------------------------------------------------------------

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d.%m.%Y",
    "%Y/%m/%d",
    "%d-%m-%Y",
)


def _parse_date_token(raw: str | None) -> date | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    s = s.replace("\u00a0", " ").strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s[:10] if len(s) >= 10 and fmt != "%Y-%m-%d" else s, fmt).date()
        except ValueError:
            continue
    # Trailing junk: "31/03/2026, ..."
    for fmt in _DATE_FORMATS:
        for cut in (10, 11, 12):
            if len(s) >= cut:
                try:
                    return datetime.strptime(s[:cut].strip(), fmt).date()
                except ValueError:
                    pass
    return None


def _parse_created_at(raw: str | None) -> date | None:
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")[:19]).date()
    except ValueError:
        return _parse_date_token(s)


# Credit/return invoice text on ``invoice_number`` / ``notes`` (not full raw OCR in the flag).
_RETURN_DOC_RX = re.compile(
    r"საკრედიტო|დაბრუნება|უკან\s+დაბრუნება|ჩაბარება|კორექტირება|"
    r"(?<![A-Za-z])Return(?![A-Za-z])|(?<![A-Za-z])Credit(?![A-Za-z])",
    re.I | re.UNICODE,
)
# Invoice numbers like CR-… / RET-… (credit note prefixes).
_INV_NUM_CREDIT_PREFIX_RX = re.compile(r"^\s*(?:CR|RET)\b", re.I)

# Branch code: ``#`` + digits in ``stores.address`` or (fallback) in store name text.
_BRANCH_HASH_CODE_RX = re.compile(r"#\s*(\d+)")

# SQL / Python: ``stores.address`` NULL or blank → this literal (diagnostics in UI).
_MISSING_ADDRESS_MARKER = "მისამართი ბაზაში არაა"

# Supplier HQ line sometimes prepended to real ``stores.address``; must not drive ``#…`` branch codes.
# Raw forms on RS.ge: ``თბილისი,თ.ერისთავის 1`` (no space after comma) and underscore/spacing variants.
SUPPLIER_HQ_ADDRESS = "თბილისი,თ.ერისთავის 1"

# Shown when ``store_address`` is only the supplier HQ block (no store-specific tail).
_UNKNOWN_STORE_LOCATION_SNIP = "ლოკაცია დაუზუსტებელია"
_STORES_VERIFY_LOGGED = False

# Common OCR substitutions on ``stores.name`` (substring replace, order matters).
_OCR_STORE_NAME_SUBSTITUTIONS: tuple[tuple[str, str], ...] = (
    ("წიკორა", "ნიკორა"),
    ("0რი ნაბიჯი", "ორი ნაბიჯი"),
    ("Oრი ნაბიჯი", "ორი ნაბიჯი"),
    ("oრი ნაბიჯი", "ორი ნაბიჯი"),
)


def _fix_store_name_ocr_typos(series: pd.Series) -> pd.Series:
    """Normalize frequent OCR misreads in store names from the database."""
    out = series.fillna("").astype(str).map(lambda t: unicodedata.normalize("NFC", t))
    for wrong, right in _OCR_STORE_NAME_SUBSTITUTIONS:
        out = out.str.replace(wrong, right, regex=False)
    return out


def _print_stores_table_sample(conn: sqlite3.Connection) -> None:
    """Print first 5 ``stores`` rows once per process (verification / debugging)."""
    global _STORES_VERIFY_LOGGED
    if _STORES_VERIFY_LOGGED:
        return
    _STORES_VERIFY_LOGGED = True
    try:
        cur = conn.execute("SELECT * FROM stores LIMIT 5")
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        print("[AT_VERIFY_STORES_SAMPLE] First 5 rows of stores:", flush=True)
        for row in rows:
            print(dict(zip(cols, row)), flush=True)
    except sqlite3.Error as exc:
        print("[AT_VERIFY_STORES_SAMPLE] query failed:", exc, flush=True)


def _sql_ident(name: str) -> str:
    """SQLite identifier: quote only when needed."""
    n = str(name).strip()
    if not n:
        return '""'
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", n):
        return n
    return '"' + n.replace('"', '""') + '"'


def _stores_address_select_fragment(store_info_rows: list) -> str | None:
    """
    ``stores.address`` (case-insensitive): never NULL in the result set — empty DB cell
    becomes ``_MISSING_ADDRESS_MARKER`` so the UI can tell data vs code issues apart.
    """
    for row in store_info_rows:
        col = str(row[1])
        if col.lower() == "address":
            q = _sql_ident(col)
            esc = _MISSING_ADDRESS_MARKER.replace("'", "''")
            return (
                f"TRIM(COALESCE(NULLIF(TRIM(s.{q}), ''), '{esc}')) AS store_address"
            )
    return None


def _clean_address_snippet_for_ui(raw: object, max_len: int = 28) -> str:
    """Short address fragment for labels: NFC, collapse whitespace to underscores, cap length."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return ""
    s = unicodedata.normalize("NFC", str(raw)).strip()
    if not s:
        return ""
    s = re.sub(r"\s+", "_", s)
    if len(s) > max_len:
        return s[: max_len - 1] + "…"
    return s


def _strip_supplier_hq_block(s: str) -> tuple[str, bool]:
    """
    Remove the first supplier HQ fragment from a normalized address.

    Returns ``(remainder, found_hq)``. Does not touch ``_MISSING_ADDRESS_MARKER``.
    """
    if not s or s == _MISSING_ADDRESS_MARKER:
        return s, False
    needles: tuple[str, ...] = (
        SUPPLIER_HQ_ADDRESS,
        "თბილისი, თ.ერისთავის_1",
        "თბილისი,თ.ერისთავის_1",
        "თბილისი, თ.ერისთავის 1",
    )
    for needle in needles:
        if needle and needle in s:
            i = s.find(needle)
            rem = (s[:i] + s[i + len(needle) :]).strip()
            rem = re.sub(r"^\s*,\s*", "", rem)
            rem = re.sub(r"\s*,\s*$", "", rem)
            return rem.strip(), True
    # Flexible whitespace / underscore between ``ერისთავის`` and ``1``.
    rx = re.compile(r"(?:^|\s*,\s*)თბილისი\s*,\s*თ\.\s*ერისთავის[_\s]*1\s*,?\s*")
    m = rx.search(s)
    if not m:
        return s, False
    rem = (s[: m.start()] + s[m.end() :]).strip()
    rem = re.sub(r"^\s*,\s*", "", rem)
    rem = re.sub(r"\s*,\s*$", "", rem)
    return rem.strip(), True


def _store_address_display_snippet(raw: object, max_len: int = 28) -> str:
    """
    Address text for UI parentheses: strips supplier HQ; if only HQ was present, returns
    ``_UNKNOWN_STORE_LOCATION_SNIP``; otherwise a short cleaned remainder (or full address).
    """
    s = _normalize_store_address_string(raw)
    if not s:
        return ""
    if s == _MISSING_ADDRESS_MARKER:
        return _clean_address_snippet_for_ui(s, max_len)
    rem, had_hq = _strip_supplier_hq_block(s)
    if had_hq and not rem.strip():
        return _UNKNOWN_STORE_LOCATION_SNIP
    return _clean_address_snippet_for_ui(rem if had_hq else s, max_len)


def _normalize_store_address_string(address: object) -> str:
    """Unicode NFC, NBSP → space, fullwidth ``＃`` → ``#``, strip (for branch regex)."""
    if address is None or (isinstance(address, float) and pd.isna(address)):
        return ""
    s = unicodedata.normalize("NFC", str(address))
    s = s.replace("\u00a0", " ").replace("\u202f", " ").replace("\u2007", " ")
    s = s.replace("\uff03", "#")  # FULLWIDTH NUMBER SIGN → ASCII #
    return s.strip()


def _extract_store_branch_id(text: object) -> str | None:
    """
    Branch code: last ``#`` + digits in normalized text, **after** removing ``SUPPLIER_HQ_ADDRESS``
    when present (avoids picking ``#1`` from the HQ line).

    If the remainder after HQ removal is empty, returns ``None`` so ``load_invoices_enriched``
    can fall back to ``store_name`` via ``combine_first``.
    """
    s = _normalize_store_address_string(text)
    if not s:
        return None
    rem, had_hq = _strip_supplier_hq_block(s)
    search = rem if had_hq else s
    if had_hq and not search.strip():
        return None
    matches = list(_BRANCH_HASH_CODE_RX.finditer(search))
    if not matches:
        return None
    return matches[-1].group(1)


def _safe_print(*args, **kwargs) -> None:
    """Windows-safe print that handles Georgian/UTF-8 text."""
    text = " ".join(str(a) for a in args)
    try:
        print(
            text,
            **{k: v for k, v in kwargs.items() if k != "flush"},
            flush=kwargs.get("flush", False),
        )
    except UnicodeEncodeError:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))
        sys.stdout.buffer.flush()


def _debug_log_store_address_if_no_branch_code(df: pd.DataFrame) -> None:
    """When a non-empty ``store_address`` yields no ``#…`` code, log repr once per distinct string."""
    if df.empty or "store_address" not in df.columns:
        return
    seen: set[str] = set()
    for addr in df["store_address"].dropna().unique():
        norm = _normalize_store_address_string(addr)
        if not norm:
            continue
        if _extract_store_branch_id(addr) is not None:
            continue
        if norm == _MISSING_ADDRESS_MARKER:
            continue
        if norm in seen:
            continue
        seen.add(norm)
        _safe_print(
            "[AT_DEBUG_STORE_ADDRESS_NO_HASH_MATCH] branch regex found no #digits; normalized repr:",
            repr(norm)[:800],
            flush=True,
        )
        if len(seen) >= 15:
            break


def _build_store_display_name(
    chain_name: pd.Series,
    branch_id: pd.Series,
    store_address: pd.Series,
    table_store_id: pd.Series,
) -> pd.Series:
    """
    With ``#`` branch code: ``chain (#code)``.

    Otherwise a short address fragment from ``_store_address_display_snippet`` (supplier HQ
    stripped; HQ-only → ``ლოკაცია დაუზუსტებელია``), or SQL missing-address marker handling
    plus `` · ID: n`` / ``(ID: n)`` as before.
    """
    chain = chain_name.fillna("").astype(str).str.strip()
    chain = chain.replace("", "(უცნობი მაღაზია)")

    def _clean_branch(x: object) -> str | None:
        if x is None or (isinstance(x, float) and pd.isna(x)):
            return None
        t = str(x).strip()
        if not t or t.lower() in ("nan", "none", "<na>"):
            return None
        return t

    brid = branch_id.map(_clean_branch)
    has_code = brid.notna()
    from_hash = " (#" + brid.astype(str) + ")"

    addr_raw = store_address.fillna("").astype(str)
    addr_trim = addr_raw.str.strip()
    is_sentinel = addr_trim == _MISSING_ADDRESS_MARKER

    snip_series = addr_raw.map(lambda x: _store_address_display_snippet(x, 28))
    has_snip = snip_series.str.len() > 0

    tid_str = pd.to_numeric(table_store_id, errors="coerce").fillna(0).astype(int).astype(str)
    from_id_only = " (ID: " + tid_str + ")"
    snip_part = " (" + snip_series + ")"
    id_disambig = (" · ID: " + tid_str).where(is_sentinel, "")
    addr_aug = snip_part + id_disambig

    suffix = from_hash.where(has_code, addr_aug.where(~has_code & has_snip, from_id_only))
    return chain + suffix


def _warn_if_line_sales_and_returns_equal(sales_sum: float, returns_sum: float) -> None:
    """Detect pathological split where line-level sales and return GEL sums match unexpectedly."""
    if sales_sum <= 1e-9 or returns_sum <= 1e-9:
        return
    if abs(sales_sum - returns_sum) > max(1e-6, 1e-9 * abs(sales_sum)):
        return
    print(
        "[AT_WARN_SALES_RETURNS_EQUAL] sum(sales_amt) == sum(ret_amt) on line items; "
        "check parent_invoice_is_return and _line_sales_return_gel_vectors.",
        "total_sales_lines=",
        sales_sum,
        "total_returns_lines=",
        returns_sum,
        flush=True,
    )


def _compute_parent_invoice_is_return(df: pd.DataFrame) -> pd.Series:
    """
    Invoice-level credit/return when ``invoice_number`` or ``notes`` matches Georgian/English
    credit phrases, or ``invoice_number`` starts with ``CR`` / ``RET`` (credit-note style).
    """
    idx = df.index
    out = pd.Series(False, index=idx, dtype=bool)
    if "invoice_number" in df.columns:
        s = df["invoice_number"].fillna("").astype(str)
        out = out | s.str.contains(_RETURN_DOC_RX, regex=True, na=False)
        out = out | s.str.contains(_INV_NUM_CREDIT_PREFIX_RX, regex=True, na=False)
    if "notes" in df.columns:
        s = df["notes"].fillna("").astype(str)
        out = out | s.str.contains(_RETURN_DOC_RX, regex=True, na=False)

    if "raw_text_snippet" in df.columns:
        s = df["raw_text_snippet"].fillna("").astype(str)
        out = out | s.str.contains(
            r"უკან\s*დაბრუნება|საკრედიტო|კორექტირება",
            regex=True,
            na=False,
        )

    return out.fillna(False).astype(bool)


def load_invoices_enriched(db_path: Path | None = None) -> pd.DataFrame:
    """Invoices with ``store_display_name`` / ``store_name`` (same), branch id, and credit flags."""
    with connect_readonly(db_path) as conn:
        _print_stores_table_sample(conn)
        cur = conn.execute("PRAGMA table_info(invoices)")
        have = {row[1] for row in cur.fetchall()}
        cur_s = conn.execute("PRAGMA table_info(stores)")
        store_info = cur_s.fetchall()
        addr_fragment = _stores_address_select_fragment(store_info)
        parts = [
            "i.id AS invoice_id",
            "i.store_id AS store_id",
            "TRIM(COALESCE(s.name, '')) AS store_name",
            "i.invoice_date AS invoice_date_raw",
            "i.subtotal AS invoice_subtotal",
            "i.total AS invoice_total",
            "i.created_at AS created_at_raw",
        ]
        if addr_fragment:
            parts.append(addr_fragment)
        else:
            print(
                "[AT_WARN_STORE_ADDRESS_COL_MISSING] stores table has no `address` column "
                "(case-insensitive); cannot read …#317 from DB for branch labels.",
                flush=True,
            )
        if "invoice_number" in have:
            parts.append("i.invoice_number AS invoice_number")
        if "source_file" in have:
            parts.append("i.source_file AS source_file")
        if "notes" in have:
            parts.append("i.notes AS notes")
        if "raw_text" in have:
            parts.append("substr(COALESCE(i.raw_text, ''), 1, 5000) AS raw_text_snippet")
        for c in ("is_return", "is_credit", "credit_note", "invoice_type", "document_type", "kind"):
            if c in have:
                parts.append(f"i.{c} AS {c}")
        q = "SELECT\n    " + ",\n    ".join(parts) + "\nFROM invoices i\nLEFT JOIN stores s ON s.id = i.store_id"
        df = pd.read_sql_query(q, conn)
    if "store_address" not in df.columns:
        df["store_address"] = _MISSING_ADDRESS_MARKER
    if df.empty:
        df["effective_date"] = pd.Series(dtype="datetime64[ns]")
        df["revenue_gel"] = pd.Series(dtype=float)
        df["parent_invoice_is_return"] = pd.Series(dtype=bool)
        df["store_branch_id"] = pd.Series(dtype=object)
        df["store_display_name"] = pd.Series(dtype=object)
        df["store_name"] = pd.Series(dtype=object)
        df["unique_store_key"] = pd.Series(dtype=object)
        return df

    parsed_inv = df["invoice_date_raw"].map(_parse_date_token)
    parsed_created = df["created_at_raw"].map(_parse_created_at)
    eff = parsed_inv.where(parsed_inv.notna(), parsed_created)
    df["effective_date"] = pd.to_datetime(eff, errors="coerce").dt.normalize()
    df["revenue_gel"] = df["invoice_total"].fillna(df["invoice_subtotal"]).fillna(0.0).astype(float)
    df["parent_invoice_is_return"] = _compute_parent_invoice_is_return(df)
    df["store_name"] = _fix_store_name_ocr_typos(df["store_name"].fillna("").astype(str))
    df["chain_store_name"] = df["store_name"].str.strip()
    df["chain_store_name"] = df["chain_store_name"].replace("", "(უცნობი მაღაზია)")
    branch_from_addr = (
        df["store_address"].map(_extract_store_branch_id)
        if "store_address" in df.columns
        else pd.Series(pd.NA, index=df.index, dtype=object)
    )
    branch_from_name = df["store_name"].map(_extract_store_branch_id)
    df["store_branch_id"] = branch_from_addr.combine_first(branch_from_name)
    if "store_address" in df.columns:
        _debug_log_store_address_if_no_branch_code(df)
    df["store_display_name"] = _build_store_display_name(
        df["chain_store_name"],
        df["store_branch_id"],
        df["store_address"],
        df["store_id"],
    )
    df["unique_store_key"] = df["store_display_name"]
    df["store_name"] = df["store_display_name"]
    return df


def load_line_items(db_path: Path | None = None) -> pd.DataFrame:
    """Line items; includes ``unit_price`` and optional ``is_return`` / ``is_credit`` if present in DB."""
    extra_cols = ""
    with connect_readonly(db_path) as conn:
        cur = conn.execute("PRAGMA table_info(invoice_items)")
        have = {row[1] for row in cur.fetchall()}
        opt = []
        for c in ("is_return", "is_credit"):
            if c in have:
                opt.append(f"ii.{c} AS {c}")
        if opt:
            extra_cols = ",\n    " + ",\n    ".join(opt)
        q = _SQL_LINE_ITEMS_SELECT.format(extra_cols=extra_cols)
        return pd.read_sql_query(q, conn)


def load_dashboard_frames(db_path: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Invoices (with ``effective_date``) + line items joined to invoice dates / store."""
    inv = load_invoices_enriched(db_path)
    lines = load_line_items(db_path)
    if inv.empty:
        lines = lines.assign(
            effective_date=pd.NaT,
            store_id=pd.NA,
            store_name="",
            store_display_name="",
            parent_invoice_is_return=False,
        )
        return inv, lines
    if "parent_invoice_is_return" not in inv.columns:
        inv = inv.assign(parent_invoice_is_return=False)
    if "store_display_name" not in inv.columns:
        if "store_name" in inv.columns:
            inv = inv.assign(store_display_name=inv["store_name"])
        else:
            inv = inv.assign(store_display_name="(უცნობი მაღაზია)")
    meta = inv[
        [
            "invoice_id",
            "effective_date",
            "store_id",
            "store_name",
            "store_display_name",
            "parent_invoice_is_return",
        ]
    ].drop_duplicates(subset=["invoice_id"])
    lines_m = lines.merge(meta, on="invoice_id", how="left")
    lines_m["parent_invoice_is_return"] = lines_m["parent_invoice_is_return"].fillna(False).astype(bool)
    return inv, lines_m


def _invoice_store_display_merge_keys(inv_f: pd.DataFrame) -> pd.DataFrame:
    """``invoice_id`` + ``store_display_name`` for joining lines (avoids KeyError)."""
    d = inv_f.copy()
    if "store_display_name" not in d.columns:
        if "store_name" in d.columns:
            d = d.assign(store_display_name=d["store_name"])
        else:
            d = d.assign(store_display_name="(უცნობი მაღაზია)")
    return d[["invoice_id", "store_display_name"]].drop_duplicates(subset=["invoice_id"])


def _ensure_store_display_on_lines(lf: pd.DataFrame) -> pd.DataFrame:
    if "store_display_name" not in lf.columns:
        lf = lf.copy()
        lf["store_display_name"] = (
            lf["store_name"] if "store_name" in lf.columns else "(უცნობი მაღაზია)"
        )
    return lf


def _warn_credit_in_raw_when_returns_zero(inv_f: pd.DataFrame, total_returns: float) -> None:
    """If returns are ~0 but OCR raw text mentions credit, log one row for tuning."""
    if total_returns > 1e-9 or inv_f.empty:
        return
    if "raw_text_snippet" not in inv_f.columns:
        return
    marker = "საკრედიტო"
    raw = inv_f["raw_text_snippet"].fillna("").astype(str)
    has_mark = raw.str.contains(marker, regex=False, na=False)
    not_flagged = ~inv_f["parent_invoice_is_return"].fillna(False).astype(bool)
    hit = inv_f.loc[has_mark & not_flagged]
    if hit.empty:
        return
    r0 = hit.iloc[0]
    print(
        "[AT_WARN_CREDIT_IN_RAW_ZERO_RETURNS] total_returns≈0 but raw_text contains "
        "'საკრედიტო'; invoice not flagged by invoice_number/notes rules.",
        "invoice_id=",
        r0.get("invoice_id"),
        "invoice_number=",
        str(r0.get("invoice_number", ""))[:160],
        "notes_snip=",
        str(r0.get("notes", ""))[:220],
        flush=True,
    )


# ---------------------------------------------------------------------------
# Filtered aggregates (used by KPIs & charts)
# ---------------------------------------------------------------------------


def _line_sales_return_gel_vectors(lf: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """
    Split each line into sales vs return GEL (returns ≥ 0).

    - If ``parent_invoice_is_return`` is True: ``sales_amt = 0``,
      ``ret_amt = abs(line_total)`` (falls back to ``|qty|·|unit_price|`` when line_total is ~0).
    - Else (regular invoice): ``sales_amt = max(line_total, 0)``, ``ret_amt = 0`` — no mixing
      with line-level heuristics so totals stay aligned with strict parent detection.
    """
    n = len(lf)
    inv_credit = np.zeros(n, dtype=bool)
    if n and "parent_invoice_is_return" in lf.columns:
        inv_credit = lf["parent_invoice_is_return"].fillna(False).astype(bool).to_numpy()

    qtyv = np.nan_to_num(
        pd.to_numeric(lf["quantity"], errors="coerce").to_numpy(dtype=float),
        nan=0.0,
    )
    ltv_raw = pd.to_numeric(lf["line_total"], errors="coerce").to_numpy(dtype=float)
    ltv = np.nan_to_num(ltv_raw, nan=0.0)
    if "unit_price" in lf.columns:
        upv = np.nan_to_num(
            pd.to_numeric(lf["unit_price"], errors="coerce").to_numpy(dtype=float),
            nan=0.0,
        )
    else:
        upv = np.zeros_like(qtyv)
    implied = np.abs(qtyv) * np.abs(upv)
    line_value = np.where((qtyv < 0) & (np.abs(ltv) < 1e-12), implied, ltv)
    credit_amt = np.where(np.abs(line_value) > 1e-12, np.abs(line_value), implied)

    sales_amt = np.where(inv_credit, 0.0, np.maximum(line_value, 0.0))
    ret_amt = np.where(inv_credit, credit_amt, 0.0)
    return sales_amt, ret_amt


def filter_by_date_range(
    df: pd.DataFrame,
    col: str,
    start: date,
    end: date,
) -> pd.DataFrame:
    if df.empty or col not in df.columns:
        return df
    s = pd.Timestamp(start).normalize()
    e = pd.Timestamp(end).normalize()
    d = pd.to_datetime(df[col], errors="coerce").dt.normalize()
    return df[(d >= s) & (d <= e)]


def _mask_invoices_in_period(invoices: pd.DataFrame, start: date, end: date) -> pd.Series:
    """
    Rows to include for line-based returns/sales and matching KPI slice.

    Uses ``effective_date`` when it falls in [start, end]. If that is missing (NaT)
    but ``created_at`` parses into the window, the invoice still counts so credit
    lines are not dropped only because OCR left the invoice date blank.
    """
    if invoices.empty:
        return pd.Series(dtype=bool)
    s = pd.Timestamp(start).normalize()
    e = pd.Timestamp(end).normalize()
    eff = pd.to_datetime(invoices["effective_date"], errors="coerce").dt.normalize()
    created_dates = invoices["created_at_raw"].map(_parse_created_at)
    cd = pd.to_datetime(created_dates, errors="coerce").dt.normalize()
    in_eff = eff.notna() & (eff >= s) & (eff <= e)
    fallback_created = eff.isna() & cd.notna() & (cd >= s) & (cd <= e)
    return in_eff | fallback_created


def _debug_print_if_returns_zero(inv_f: pd.DataFrame, total_returns: float) -> None:
    """One console line when returns KPI is ~0: sample ``raw_text_snippet`` for OCR tuning."""
    if total_returns > 1e-9 or inv_f.empty:
        return
    if "raw_text_snippet" not in inv_f.columns:
        return
    miss = inv_f.loc[~inv_f["parent_invoice_is_return"].astype(bool)]
    txt = miss["raw_text_snippet"].fillna("").astype(str)
    miss = miss.loc[txt.str.len() > 40]
    if miss.empty:
        miss = inv_f.loc[~inv_f["parent_invoice_is_return"].astype(bool)]
    if miss.empty:
        return
    row = miss.iloc[0]
    print(
        "[AT_DEBUG_RETURNS_ZERO] invoice_id=",
        row.get("invoice_id"),
        "raw_text_snippet=",
        str(row.get("raw_text_snippet"))[:900],
        flush=True,
    )


def kpi_bundle(
    invoices: pd.DataFrame,
    lines: pd.DataFrame,
    start: date,
    end: date,
) -> dict[str, Any]:
    mask = _mask_invoices_in_period(invoices, start, end)
    inv_f = invoices.loc[mask].copy()
    if inv_f.empty:
        ids: set[int] = set()
    else:
        ids = set(
            pd.to_numeric(inv_f["invoice_id"], errors="coerce").dropna().astype(int).tolist()
        )

    if not ids:
        return {
            "total_revenue_gel": 0.0,
            "total_returns_gel": 0.0,
            "returns_pct": 0.0,
            "n_stores": 0,
        }

    li = pd.to_numeric(lines["invoice_id"], errors="coerce")
    lines_f = lines.loc[li.isin(ids)].copy()
    sales_v, ret_v = _line_sales_return_gel_vectors(lines_f)
    total_returns = float(ret_v.sum())
    _warn_if_line_sales_and_returns_equal(float(sales_v.sum()), total_returns)
    total_revenue = float(inv_f["revenue_gel"].sum())
    ret_pct = (total_returns / total_revenue * 100.0) if total_revenue > 0 else 0.0
    _warn_credit_in_raw_when_returns_zero(inv_f, total_returns)
    _debug_print_if_returns_zero(inv_f, total_returns)
    if "store_display_name" in inv_f.columns:
        n_stores = int(inv_f["store_display_name"].nunique())
    else:
        n_stores = int(inv_f["store_id"].nunique())
    return {
        "total_revenue_gel": round(total_revenue, 2),
        "total_returns_gel": round(total_returns, 2),
        "returns_pct": round(ret_pct, 2),
        "n_stores": n_stores,
    }


def revenue_by_store(
    invoices: pd.DataFrame,
    start: date,
    end: date,
) -> pd.DataFrame:
    inv_f = filter_by_date_range(invoices, "effective_date", start, end)
    if inv_f.empty:
        return pd.DataFrame(columns=["store_name", "revenue_gel"])
    gcol = "store_display_name" if "store_display_name" in inv_f.columns else "store_name"
    g = (
        inv_f.groupby(gcol, as_index=False)["revenue_gel"]
        .sum()
        .sort_values("revenue_gel", ascending=False)
        .rename(columns={gcol: "store_name"})
    )
    g["revenue_gel"] = g["revenue_gel"].round(2)
    return g


def top_products_by_quantity(
    invoices: pd.DataFrame,
    lines: pd.DataFrame,
    start: date,
    end: date,
    top_n: int = 15,
) -> pd.DataFrame:
    inv_f = filter_by_date_range(invoices, "effective_date", start, end)
    if inv_f.empty:
        return pd.DataFrame(columns=["product_label", "quantity", "sales_gel", "pct_of_sales"])
    ids = set(inv_f["invoice_id"].astype(int))
    lf = lines[lines["invoice_id"].isin(ids)].copy()
    if "store_display_name" in lf.columns:
        lf = lf.drop(columns=["store_display_name"])
    invk = _invoice_store_display_merge_keys(inv_f)
    lf = lf.merge(invk, on="invoice_id", how="left")
    lf = _ensure_store_display_on_lines(lf)
    lf["store_display_name"] = lf["store_display_name"].fillna("(უცნობი მაღაზია)")
    lf["product_label"] = lf["store_display_name"].astype(str) + " · " + lf["product_label"].astype(str)
    lf["qty"] = lf["quantity"].fillna(0.0).astype(float)
    lf["sales_row"] = lf["line_total"].clip(lower=0).fillna(0.0).astype(float)
    total_sales = float(lf["sales_row"].sum()) or 1.0
    g = (
        lf.groupby("product_label", as_index=False)
        .agg(quantity=("qty", "sum"), sales_gel=("sales_row", "sum"))
        .sort_values("quantity", ascending=False)
        .head(top_n)
    )
    g["pct_of_sales"] = (g["sales_gel"] / total_sales * 100.0).round(2)
    g["quantity"] = g["quantity"].round(2)
    g["sales_gel"] = g["sales_gel"].round(2)
    return g


def returns_vs_sales_by_store(
    invoices: pd.DataFrame,
    lines: pd.DataFrame,
    start: date,
    end: date,
) -> pd.DataFrame:
    mask = _mask_invoices_in_period(invoices, start, end)
    inv_f = invoices.loc[mask].copy()
    if inv_f.empty:
        return pd.DataFrame(columns=["store_name", "sales_gel", "returns_gel"])
    ids = set(
        pd.to_numeric(inv_f["invoice_id"], errors="coerce").dropna().astype(int).tolist()
    )
    li = pd.to_numeric(lines["invoice_id"], errors="coerce")
    lf = lines.loc[li.isin(ids)].copy()
    # ``invoice_items`` rows do not carry ``store_name`` / parent credit flag; join from invoices.
    if "store_display_name" in lf.columns:
        lf = lf.drop(columns=["store_display_name"])
    if "store_name" in lf.columns:
        lf = lf.drop(columns=["store_name"])
    if "parent_invoice_is_return" in lf.columns:
        lf = lf.drop(columns=["parent_invoice_is_return"])
    if "parent_invoice_is_return" not in inv_f.columns:
        inv_f = inv_f.assign(parent_invoice_is_return=False)
    meta_cols = ["invoice_id", "parent_invoice_is_return"]
    if "store_display_name" in inv_f.columns:
        meta_cols.insert(1, "store_display_name")
    else:
        meta_cols.insert(1, "store_name")
    inv_meta = (
        inv_f[meta_cols]
        .drop_duplicates(subset=["invoice_id"])
        .assign(invoice_id=lambda d: pd.to_numeric(d["invoice_id"], errors="coerce"))
    )
    lf = lf.assign(invoice_id=lambda d: pd.to_numeric(d["invoice_id"], errors="coerce"))
    lf = lf.merge(inv_meta, on="invoice_id", how="left")
    gcol = "store_display_name" if "store_display_name" in lf.columns else "store_name"
    lf[gcol] = lf[gcol].fillna("(უცნობი მაღაზია)")
    lf["parent_invoice_is_return"] = lf["parent_invoice_is_return"].fillna(False).astype(bool)
    if os.environ.get("AT_DEBUG_RETURNS", "").strip().lower() in ("1", "true", "yes", "on"):
        print(
            "[AT_DEBUG_RETURNS]",
            "n_lines=",
            len(lf),
            "line_total[:20]=",
            lf["line_total"].head(20).tolist(),
            "quantity[:20]=",
            lf["quantity"].head(20).tolist(),
            "unit_price[:20]=",
            lf["unit_price"].head(20).tolist() if "unit_price" in lf.columns else None,
            "parent_invoice_is_return[:20]=",
            lf["parent_invoice_is_return"].head(20).tolist()
            if "parent_invoice_is_return" in lf.columns
            else None,
            flush=True,
        )
    sales_v, ret_v = _line_sales_return_gel_vectors(lf)
    lf = lf.assign(
        _sales=pd.Series(sales_v, index=lf.index, dtype=float),
        _ret=pd.Series(ret_v, index=lf.index, dtype=float),
    )
    g = (
        lf.groupby(gcol, as_index=False)
        .agg(sales_gel=("_sales", "sum"), returns_gel=("_ret", "sum"))
        .sort_values("sales_gel", ascending=False)
        .rename(columns={gcol: "store_name"})
    )
    g["sales_gel"] = g["sales_gel"].round(2)
    g["returns_gel"] = g["returns_gel"].clip(lower=0.0).round(2)
    return g


def returns_debug_line_sample(
    invoices: pd.DataFrame,
    lines: pd.DataFrame,
    start: date,
    end: date,
    n: int = 25,
) -> pd.DataFrame:
    """Small slice of line rows in the returns window for UI/debug (Streamlit ``st.dataframe``)."""
    mask = _mask_invoices_in_period(invoices, start, end)
    inv_f = invoices.loc[mask]
    if inv_f.empty:
        return pd.DataFrame()
    ids = set(pd.to_numeric(inv_f["invoice_id"], errors="coerce").dropna().astype(int))
    li = pd.to_numeric(lines["invoice_id"], errors="coerce")
    lf = lines.loc[li.isin(ids)].copy()
    lf["invoice_id"] = pd.to_numeric(lf["invoice_id"], errors="coerce")
    inv_f2 = inv_f.copy()
    if "parent_invoice_is_return" not in inv_f2.columns:
        inv_f2 = inv_f2.assign(parent_invoice_is_return=False)
    cols = ["invoice_id", "parent_invoice_is_return"]
    for c in ("store_name", "unique_store_key"):
        if c in inv_f2.columns:
            cols.append(c)
    inv_key = inv_f2[cols].drop_duplicates(subset=["invoice_id"]).copy()
    inv_key["invoice_id"] = pd.to_numeric(inv_key["invoice_id"], errors="coerce")
    lf = lf.merge(inv_key, on="invoice_id", how="left")
    lf["parent_invoice_is_return"] = lf["parent_invoice_is_return"].fillna(False).astype(bool)
    want = [
        "invoice_id",
        "store_name",
        "unique_store_key",
        "quantity",
        "unit_price",
        "line_total",
        "product_label",
        "parent_invoice_is_return",
        "is_return",
        "is_credit",
    ]
    cols = [c for c in want if c in lf.columns]
    return lf[cols].head(int(n)) if cols else lf.head(int(n))


def period_calendar_days(start: date, end: date) -> int:
    """Inclusive day count for rate calculations."""
    return max(1, (end - start).days + 1)


def daily_revenue_series(
    invoices: pd.DataFrame,
    start: date,
    end: date,
) -> pd.DataFrame:
    """One row per calendar day: invoice-header revenue (GEL)."""
    inv_f = filter_by_date_range(invoices, "effective_date", start, end)
    if inv_f.empty:
        return pd.DataFrame(columns=["day", "revenue_gel"])
    x = inv_f.copy()
    x["day"] = pd.to_datetime(x["effective_date"], errors="coerce").dt.normalize()
    return (
        x.groupby("day", as_index=False)["revenue_gel"]
        .sum()
        .sort_values("day")
        .assign(revenue_gel=lambda d: d["revenue_gel"].round(2))
    )


def daily_sales_returns_series(
    invoices: pd.DataFrame,
    lines: pd.DataFrame,
    start: date,
    end: date,
) -> pd.DataFrame:
    """One row per calendar day: line-level sales vs returns GEL (hero area chart)."""
    mask = _mask_invoices_in_period(invoices, start, end)
    inv_f = invoices.loc[mask].copy()
    if inv_f.empty:
        return pd.DataFrame(columns=["day", "sales_gel", "returns_gel"])
    ids = set(pd.to_numeric(inv_f["invoice_id"], errors="coerce").dropna().astype(int).tolist())
    li = pd.to_numeric(lines["invoice_id"], errors="coerce")
    lf = lines.loc[li.isin(ids)].copy()
    if lf.empty:
        return pd.DataFrame(columns=["day", "sales_gel", "returns_gel"])
    for col in ("effective_date", "parent_invoice_is_return"):
        if col in lf.columns:
            lf = lf.drop(columns=[col])
    if "parent_invoice_is_return" not in inv_f.columns:
        inv_f = inv_f.assign(parent_invoice_is_return=False)
    inv_meta = (
        inv_f[["invoice_id", "effective_date", "parent_invoice_is_return"]]
        .drop_duplicates(subset=["invoice_id"])
        .assign(invoice_id=lambda d: pd.to_numeric(d["invoice_id"], errors="coerce"))
    )
    lf = lf.assign(invoice_id=lambda d: pd.to_numeric(d["invoice_id"], errors="coerce"))
    lf = lf.merge(inv_meta, on="invoice_id", how="left")
    lf["parent_invoice_is_return"] = lf["parent_invoice_is_return"].fillna(False).astype(bool)
    sales_v, ret_v = _line_sales_return_gel_vectors(lf)
    lf = lf.assign(_s=sales_v, _r=ret_v)
    lf["day"] = pd.to_datetime(lf["effective_date"], errors="coerce").dt.normalize()
    lf = lf.loc[lf["day"].notna()]
    if lf.empty:
        return pd.DataFrame(columns=["day", "sales_gel", "returns_gel"])
    g = (
        lf.groupby("day", as_index=False)
        .agg(sales_gel=("_s", "sum"), returns_gel=("_r", "sum"))
        .sort_values("day")
    )
    g["sales_gel"] = g["sales_gel"].round(2)
    g["returns_gel"] = g["returns_gel"].clip(lower=0.0).round(2)
    return g


def store_share_with_returns_pct(
    invoices: pd.DataFrame,
    lines: pd.DataFrame,
    start: date,
    end: date,
) -> pd.DataFrame:
    """
    Per store: invoice revenue (for donut share), line-level sales & returns,
    return rate % of positive line sales.
    """
    rev = revenue_by_store(invoices, start, end)
    rsr = returns_vs_sales_by_store(invoices, lines, start, end)
    if rev.empty:
        return pd.DataFrame(
            columns=[
                "store_name",
                "revenue_gel",
                "sales_gel",
                "returns_gel",
                "return_pct",
                "share_pct",
            ]
        )
    m = rev.merge(rsr, on="store_name", how="left")
    m["returns_gel"] = m["returns_gel"].fillna(0.0)
    m["sales_gel"] = m["sales_gel"].fillna(0.0)
    tot = float(m["revenue_gel"].sum()) or 1.0
    m["share_pct"] = (m["revenue_gel"] / tot * 100.0).round(2)
    den = m["sales_gel"].replace(0, pd.NA)
    m["return_pct"] = ((m["returns_gel"] / den) * 100.0).fillna(0.0).round(2)
    return m


def all_products_by_quantity_share(
    invoices: pd.DataFrame,
    lines: pd.DataFrame,
    start: date,
    end: date,
) -> pd.DataFrame:
    """Per-store product rows: ``store (#id) · product`` so branches do not merge in the chart."""
    inv_f = filter_by_date_range(invoices, "effective_date", start, end)
    if inv_f.empty:
        return pd.DataFrame(
            columns=["product_label", "quantity", "sales_gel", "pct_of_total_qty"]
        )
    ids = set(inv_f["invoice_id"].astype(int))
    lf = lines[lines["invoice_id"].isin(ids)].copy()
    if "store_display_name" in lf.columns:
        lf = lf.drop(columns=["store_display_name"])
    invk = _invoice_store_display_merge_keys(inv_f)
    lf = lf.merge(invk, on="invoice_id", how="left")
    lf = _ensure_store_display_on_lines(lf)
    lf["store_display_name"] = lf["store_display_name"].fillna("(უცნობი მაღაზია)")
    lf["product_label"] = lf["store_display_name"].astype(str) + " · " + lf["product_label"].astype(str)
    lf["qty"] = lf["quantity"].fillna(0.0).astype(float)
    lf["sales_row"] = lf["line_total"].clip(lower=0).fillna(0.0).astype(float)
    g = (
        lf.groupby("product_label", as_index=False)
        .agg(quantity=("qty", "sum"), sales_gel=("sales_row", "sum"))
        .sort_values("quantity", ascending=False)
    )
    tq = float(g["quantity"].sum()) or 1.0
    g["pct_of_total_qty"] = (g["quantity"] / tq * 100.0).round(2)
    g["quantity"] = g["quantity"].round(2)
    g["sales_gel"] = g["sales_gel"].round(2)
    return g


def restock_recommendations_by_store(
    invoices: pd.DataFrame,
    start: date,
    end: date,
) -> pd.DataFrame:
    """
    Heuristic restock hint: avg daily invoice revenue × 1.75 (~1–2 days cover).

    ``confidence_pct`` is deterministic in [70, 80] from store + period hash.
    """
    inv_f = filter_by_date_range(invoices, "effective_date", start, end)
    if inv_f.empty:
        return pd.DataFrame(
            columns=[
                "store_name",
                "avg_daily_revenue_gel",
                "recommended_restock_gel",
                "confidence_pct",
            ]
        )
    inv_f = inv_f.copy()
    if "store_display_name" in inv_f.columns:
        inv_f["store_display_name"] = _fix_store_name_ocr_typos(inv_f["store_display_name"])
    inv_f = inv_f.copy()
    if "store_display_name" in inv_f.columns:
        inv_f["store_display_name"] = _fix_store_name_ocr_typos(inv_f["store_display_name"])
    elif "store_name" in inv_f.columns:
        inv_f["store_name"] = _fix_store_name_ocr_typos(inv_f["store_name"])
    days = period_calendar_days(start, end)
    gcol = "store_display_name" if "store_display_name" in inv_f.columns else "store_name"
    g = (
        inv_f.groupby(gcol, as_index=False)["revenue_gel"]
        .sum()
        .rename(columns={gcol: "store_name"})
    )
    g["avg_daily_revenue_gel"] = (g["revenue_gel"] / days).round(2)
    g["recommended_restock_gel"] = (g["avg_daily_revenue_gel"] * 1.75).round(2)

    def _conf(row: pd.Series) -> int:
        raw = f"{row['store_name']}|{start}|{end}"
        h = int(hashlib.md5(raw.encode("utf-8")).hexdigest()[:8], 16)
        return 70 + (h % 11)

    g["confidence_pct"] = g.apply(_conf, axis=1)
    return g.sort_values("recommended_restock_gel", ascending=False)


_VALID_PRESET_LABELS = frozenset(
    {
        "7 Days",
        "7 დღე",
        "15 Days",
        "15 დღე",
        "1 Month",
        "1 თვე",
        "6 Months",
        "6 თვე",
        "1 Year",
        "1 წელი",
    }
)


def preset_range(label: str, end: date | None = None) -> tuple[date, date]:
    """Map preset label (Georgian or English) to inclusive (start, end)."""
    e = end or date.today()
    if label not in _VALID_PRESET_LABELS:
        label = "1 თვე"
    presets: dict[str, int] = {
        "7 Days": 7,
        "7 დღე": 7,
        "15 Days": 15,
        "15 დღე": 15,
        "1 Month": 30,
        "1 თვე": 30,
        "6 Months": 183,
        "6 თვე": 183,
        "1 Year": 365,
        "1 წელი": 365,
    }
    if label not in presets:
        label = "1 თვე"
    delta = presets[label]
    return e - timedelta(days=delta - 1), e

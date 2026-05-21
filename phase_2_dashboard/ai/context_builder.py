"""
Build per-session AI context from ``data_loader`` only (no SQL).

Respects ``get_allowed_store_ids()`` — distributors never see other stores' data.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import pandas as pd

from auth.auth import get_allowed_store_ids, get_current_user
from data_loader import (
    filter_by_date_range,
    kpi_bundle,
    load_dashboard_frames,
    preset_range,
    restock_recommendations_by_store,
    revenue_by_store,
    top_products_by_quantity,
)

_STORE_KEYWORDS = (
    "ნიკორა",
    "ორი ნაბიჯი",
    "ზღაპარი",
    "ლაქი",
    "სმარტ",
    "გვირილა",
    "რითეილ",
    "მოტორს",
    "მ.ა.მ",
)


def _filter_frames(
    inv: pd.DataFrame,
    lines: pd.DataFrame,
    allowed_store_ids: frozenset[int] | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if allowed_store_ids is None:
        return inv, lines
    if not allowed_store_ids:
        return inv.iloc[0:0].copy(), lines.iloc[0:0].copy()
    inv_f = inv[inv["store_id"].isin(allowed_store_ids)].copy()
    if inv_f.empty:
        return inv_f, lines.iloc[0:0].copy()
    if "store_id" in lines.columns:
        lines_f = lines[lines["store_id"].isin(allowed_store_ids)].copy()
    else:
        lines_f = lines[lines["invoice_id"].isin(inv_f["invoice_id"])].copy()
    return inv_f, lines_f


def _format_kpi(kpi: dict[str, Any]) -> str:
    return (
        f"total_revenue_gel={kpi['total_revenue_gel']}\n"
        f"total_returns_gel={kpi['total_returns_gel']}\n"
        f"returns_pct={kpi['returns_pct']}\n"
        f"n_stores={kpi['n_stores']}"
    )


def _format_restock(df: pd.DataFrame, limit: int = 8) -> str:
    if df.empty:
        return "(ცარიელი)"
    lines = []
    for _, r in df.head(limit).iterrows():
        lines.append(
            f"- {r['store_name']}: რეკ. მარაგი {r['recommended_restock_gel']} GEL, "
            f"საშ. დღ. {r['avg_daily_revenue_gel']} GEL, confidence {r['confidence_pct']}%"
        )
    return "\n".join(lines)


def _format_revenue_stores(df: pd.DataFrame, limit: int = 8) -> str:
    if df.empty:
        return "(ცარიელი)"
    return "\n".join(
        f"- {r['store_name']}: {r['revenue_gel']} GEL"
        for _, r in df.head(limit).iterrows()
    )


def _format_top_products(df: pd.DataFrame, limit: int = 8) -> str:
    if df.empty:
        return "(ცარიელი)"
    return "\n".join(
        f"- {r['product_label']}: qty={r['quantity']}, sales={r['sales_gel']} GEL"
        for _, r in df.head(limit).iterrows()
    )


def _store_focus_block(
    inv: pd.DataFrame,
    lines: pd.DataFrame,
    prompt: str,
    start: date,
    end: date,
) -> str:
    """Optional store-specific slice using user's scoped frames only."""
    if inv.empty:
        return ""

    name_col = "store_display_name" if "store_display_name" in inv.columns else "store_name"
    mask = pd.Series(False, index=inv.index)
    for kw in _STORE_KEYWORDS:
        if kw in prompt:
            mask = mask | inv[name_col].astype(str).str.contains(kw, case=False, na=False)
    hash_match = re.search(r"#(\d+)", prompt)
    if hash_match:
        branch = f"#{hash_match.group(1)}"
        mask = mask | inv[name_col].astype(str).str.contains(branch, regex=False, na=False)

    if not mask.any():
        return ""

    inv_s = inv.loc[mask]
    ids = set(inv_s["invoice_id"].astype(int))
    lines_s = lines[lines["invoice_id"].isin(ids)] if not lines.empty else lines
    inv_p = filter_by_date_range(inv_s, "effective_date", start, end)
    if inv_p.empty:
        return "კონკრეტული მაღაზია: პერიოდში ჩანაწერი ვერ მოიძებნა."

    gcol = name_col
    store_name = str(inv_p[gcol].iloc[0])
    kpi = kpi_bundle(inv_p, lines_s, start, end)
    top = top_products_by_quantity(inv_p, lines_s, start, end, top_n=5)
    restock = restock_recommendations_by_store(inv_p, start, end)

    return f"""
### მაღაზიის ფოკუსი: {store_name}
KPI (ფოკუსი):
{_format_kpi(kpi)}
ტოპ პროდუქტები:
{_format_top_products(top, 5)}
მარაგის რჩევა:
{_format_restock(restock, 3)}
"""


def build_session_context(
    user_prompt: str,
    *,
    period_label: str = "1 თვე",
) -> str:
    """
    Aggregated, scope-safe context string for the user message (not cached).
    """
    user = get_current_user()
    if user is None:
        return "<session_context>\nunauthorized\n</session_context>"

    allowed = get_allowed_store_ids()
    start, end = preset_range(period_label)

    inv, lines = load_dashboard_frames()
    inv, lines = _filter_frames(inv, lines, allowed)

    if allowed is not None and inv.empty:
        return f"""<session_context>
user_id={user['id']}
role={user['role']}
store_ids=[]
period={start} .. {end}
status=NO_ASSIGNED_STORE_DATA
</session_context>"""

    kpi = kpi_bundle(inv, lines, start, end)
    rev = revenue_by_store(inv, start, end)
    restock = restock_recommendations_by_store(inv, start, end)
    top = top_products_by_quantity(inv, lines, start, end, top_n=8)

    store_ids_repr = (
        "ALL"
        if allowed is None
        else ",".join(str(x) for x in sorted(allowed))
    )

    focus = _store_focus_block(inv, lines, user_prompt, start, end)

    return f"""<session_context>
user_id={user['id']}
role={user['role']}
display_name={user.get('display_name', user['username'])}
store_ids={store_ids_repr}
period={start} .. {end}
invoice_rows={len(inv)}
line_rows={len(lines)}

### KPI (პერიოდი)
{_format_kpi(kpi)}

### შემოსავალი მაღაზიებით (ტოპ)
{_format_revenue_stores(rev)}

### მარაგის რეკომენდაცია
{_format_restock(restock)}

### ტოპ პროდუქტები
{_format_top_products(top)}
{focus}
</session_context>"""

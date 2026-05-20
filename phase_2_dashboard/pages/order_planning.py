"""
Smart Order Planning — distributor's daily order guide.
Shows per-store, per-product recommendations based on sales history.
"""

from __future__ import annotations

import html
import sqlite3
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from data_loader import resolve_db_path
from ui_theme import (
    ACCENT,
    BG,
    BORDER,
    CARD,
    CARD_PADDING,
    DANGER,
    FONT_BODY,
    FONT_HEADING,
    FONT_NUMBERS,
    GOOGLE_FONTS_URL,
    MUTED,
    PRIMARY,
    RADIUS,
    SUCCESS,
    TEXT,
    WARNING,
    _logo_b64,
    apply_watermark,
)

BREAD_SHELF_LIFE = {
    "default": 6,
    "შავი": 7,
    "რუხი": 7,
    "dark": 7,
}

_RETURN_SQL = """
    AND (i.notes IS NULL OR (
        i.notes NOT LIKE '%უკან დაბრუნება%'
        AND i.notes NOT LIKE '%საკრედიტო%'
        AND i.notes NOT LIKE '%კორექტირება%'
    ))
    AND (i.invoice_number IS NULL OR (
        i.invoice_number NOT LIKE '%უკან%'
        AND i.invoice_number NOT LIKE '%credit%'
    ))
"""


def _get_shelf_life(product_name: str) -> int:
    name = product_name.lower()
    for key, days in BREAD_SHELF_LIFE.items():
        if key != "default" and key in name:
            return days
    return BREAD_SHELF_LIFE["default"]


def _load_store_history(
    store_ids: list[int],
    days_back: int = 60,
) -> pd.DataFrame:
    """Load invoice history for given stores."""
    if not store_ids:
        return pd.DataFrame()
    db_path = resolve_db_path()
    conn = sqlite3.connect(db_path)
    placeholders = ",".join("?" * len(store_ids))
    query = f"""
        SELECT
            i.store_id,
            s.name AS store_name,
            i.invoice_date,
            COALESCE(p.name, ii.description, '') AS product_name,
            ii.quantity,
            ii.line_total
        FROM invoices i
        JOIN stores s ON s.id = i.store_id
        JOIN invoice_items ii ON ii.invoice_id = i.id
        LEFT JOIN products p ON p.id = ii.product_id
        WHERE i.store_id IN ({placeholders})
          AND i.invoice_date >= date('now', '-{days_back} days')
          {_RETURN_SQL}
          AND ii.quantity > 0
        ORDER BY i.store_id, i.invoice_date DESC
    """
    df = pd.read_sql_query(query, conn, params=store_ids)
    conn.close()
    return df


def _calc_visit_frequency(df: pd.DataFrame, store_id: int) -> float:
    """Average days between visits for this store."""
    dates = df[df["store_id"] == store_id]["invoice_date"].dropna().unique()
    if len(dates) < 2:
        return 2.0
    dates_sorted = sorted(pd.to_datetime(dates))
    gaps = [
        (dates_sorted[i + 1] - dates_sorted[i]).days
        for i in range(len(dates_sorted) - 1)
        if (dates_sorted[i + 1] - dates_sorted[i]).days > 0
    ]
    return round(sum(gaps) / len(gaps), 1) if gaps else 2.0


def _calc_product_recommendations(
    df: pd.DataFrame,
    store_id: int,
    visit_freq_days: float,
) -> pd.DataFrame:
    """
    Per-product recommendation for next visit.
    Logic: daily_avg × visit_freq × 1.1 buffer.
    """
    store_df = df[df["store_id"] == store_id].copy()
    if store_df.empty:
        return pd.DataFrame()

    dates = pd.to_datetime(store_df["invoice_date"].dropna().unique())
    n_days = max(1, (dates.max() - dates.min()).days + 1)
    n_visits = len(dates)

    products: list[dict[str, object]] = []
    for product, grp in store_df.groupby("product_name"):
        if not product or len(str(product)) < 2:
            continue

        total_qty = float(grp["quantity"].sum())
        avg_per_visit = total_qty / n_visits
        daily_avg = total_qty / n_days
        recommended = daily_avg * visit_freq_days * 1.1

        if n_visits >= 15:
            confidence = 85
        elif n_visits >= 8:
            confidence = 75
        elif n_visits >= 4:
            confidence = 65
        else:
            confidence = 50

        visit_qtys = grp.groupby("invoice_date")["quantity"].sum()
        if len(visit_qtys) > 2:
            cv = visit_qtys.std() / (visit_qtys.mean() + 0.001)
            if cv < 0.3:
                confidence = min(confidence + 10, 90)
            elif cv > 0.7:
                confidence = max(confidence - 15, 40)

        products.append(
            {
                "product": product,
                "avg_per_visit": round(avg_per_visit, 1),
                "recommended_qty": max(1, round(recommended)),
                "confidence_pct": confidence,
                "shelf_life_days": _get_shelf_life(str(product)),
                "n_visits": n_visits,
            }
        )

    if not products:
        return pd.DataFrame()

    return pd.DataFrame(products).sort_values("recommended_qty", ascending=False)


def _confidence_color(pct: int) -> str:
    if pct >= 80:
        return SUCCESS
    if pct >= 65:
        return WARNING
    return DANGER


def _confidence_label(pct: int) -> str:
    if pct >= 80:
        return "მაღალი"
    if pct >= 65:
        return "საშუალო"
    return "დაბალი"


def _load_stores(allowed_store_ids: list[int] | None) -> list[tuple[int, str, str]]:
    db_path = resolve_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    if allowed_store_ids is not None:
        if not allowed_store_ids:
            conn.close()
            return []
        placeholders = ",".join("?" * len(allowed_store_ids))
        cur.execute(
            f"""
            SELECT id, name, COALESCE(address, '') FROM stores
            WHERE id IN ({placeholders})
              AND name != '(უცნობი მყიდველი)'
            ORDER BY name
            """,
            allowed_store_ids,
        )
    else:
        cur.execute(
            """
            SELECT id, name, COALESCE(address, '') FROM stores
            WHERE name != '(უცნობი მყიდველი)'
            ORDER BY name
            """
        )
    rows = [(int(r[0]), str(r[1]), str(r[2])) for r in cur.fetchall()]
    conn.close()
    return rows


def render(allowed_store_ids: list[int] | None = None) -> None:
    """Render order planning page."""
    st.markdown(
        f"""
    <style>
    @import url('{GOOGLE_FONTS_URL}');
    .stApp {{ background-color: {BG} !important; color: {TEXT} !important; font-family: {FONT_BODY}; }}
    .order-header {{
        background: {CARD};
        border: 1px solid {BORDER};
        border-radius: {RADIUS};
        padding: {CARD_PADDING};
        margin-bottom: 20px;
    }}
    .order-header:hover {{ border-color: {PRIMARY}; box-shadow: 0 0 24px rgba(0, 209, 199, 0.25); }}
    </style>
    """,
        unsafe_allow_html=True,
    )
    apply_watermark(_logo_b64(), opacity=0.04)

    today = date.today()
    tomorrow = today + timedelta(days=1)
    scope_note = (
        "ყველა მაღაზია · მენეჯერის მიმოხილვა"
        if allowed_store_ids is None
        else "თქვენი მიბმული მაღაზიები"
    )
    st.markdown(
        f"""
    <div class="order-header">
        <div style="color:{PRIMARY};font-size:0.75rem;
            text-transform:uppercase;letter-spacing:0.1em;font-family:{FONT_HEADING};">
            📋 შეკვეთის დაგეგმვა
        </div>
        <div style="font-size:1.6rem;font-weight:700;
            color:{TEXT};margin:6px 0;font-family:{FONT_HEADING};">
            {tomorrow.strftime('%d %B %Y')} — ხვალინდელი შეკვეთა
        </div>
        <div style="color:{MUTED};font-size:0.85rem;">
            ბოლო 60 დღის გაყიდვების ანალიზი · {html.escape(scope_note)}
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    stores = _load_stores(allowed_store_ids)
    if not stores:
        st.info("მაღაზიები არ მოიძებნა")
        return

    store_ids = [s[0] for s in stores]
    history_df = _load_store_history(store_ids)

    if history_df.empty:
        st.warning("გაყიდვების ისტორია არ არის ბოლო 60 დღეში")
        return

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("მაღაზიები", len(stores))
    with m2:
        avg_freq = sum(_calc_visit_frequency(history_df, s[0]) for s in stores) / len(stores)
        st.metric("საშ. ვიზიტი", f"{avg_freq:.1f} დღეში")
    with m3:
        st.metric("ანალიზის პერიოდი", "60 დღე")

    st.markdown("---")

    for store_id, store_name, store_addr in stores:
        visit_freq = _calc_visit_frequency(history_df, store_id)
        recs = _calc_product_recommendations(history_df, store_id, visit_freq)
        addr_short = html.escape((store_addr or "")[:45])

        with st.expander(
            f"🏪 {store_name}  —  ვიზიტი: {visit_freq:.0f} დღეში ერთხელ",
            expanded=False,
        ):
            if recs.empty:
                st.caption("მონაცემები არ არის")
                continue

            col1, col2 = st.columns([3, 1])
            with col1:
                st.caption(f"📍 {addr_short}")
            with col2:
                next_visit = today + timedelta(days=round(visit_freq))
                st.caption(f"შემდეგი ვიზიტი: **{next_visit.strftime('%d %b')}**")

            st.markdown("---")

            for _, row in recs.iterrows():
                conf_color = _confidence_color(int(row["confidence_pct"]))
                conf_label = _confidence_label(int(row["confidence_pct"]))
                product_esc = html.escape(str(row["product"]))
                shelf = int(row["shelf_life_days"])

                col_name, col_qty, col_conf = st.columns([4, 1, 2])
                with col_name:
                    st.markdown(
                        f"**{product_esc}**  \n"
                        f"<span style='color:#6b7280;font-size:0.78rem;'>"
                        f"საშ/ვიზიტი: {row['avg_per_visit']} ც · "
                        f"ვადა: {shelf} დღე</span>",
                        unsafe_allow_html=True,
                    )
                with col_qty:
                    st.markdown(
                        f"<div style='text-align:center;"
                        f"font-size:1.4rem;font-weight:700;"
                        f"color:{PRIMARY};font-family:{FONT_NUMBERS};'>"
                        f"{int(row['recommended_qty'])}</div>"
                        f"<div style='text-align:center;color:#6b7280;"
                        f"font-size:0.7rem;'>ცალი</div>",
                        unsafe_allow_html=True,
                    )
                with col_conf:
                    st.markdown(
                        f"<div style='text-align:center;"
                        f"background:rgba(0,0,0,0.3);"
                        f"border:1px solid {conf_color}33;"
                        f"border-radius:8px;padding:6px;'>"
                        f"<span style='color:{conf_color};"
                        f"font-weight:600;font-size:0.9rem;'>"
                        f"{row['confidence_pct']}%</span><br>"
                        f"<span style='color:#6b7280;font-size:0.7rem;'>"
                        f"{conf_label}</span></div>",
                        unsafe_allow_html=True,
                    )

            total_items = int(recs["recommended_qty"].sum())
            st.markdown(
                f"<div style='margin-top:12px;padding:10px;"
                f"background:rgba(34,211,238,0.08);"
                f"border:1px solid rgba(34,211,238,0.2);"
                f"border-radius:8px;text-align:center;'>"
                f"<span style='color:#9aa0ab;font-size:0.8rem;'>სულ შესატანი: </span>"
                f"<span style='color:{PRIMARY};font-size:1.2rem;"
                f"font-weight:700;font-family:{FONT_NUMBERS};'>{total_items} ცალი</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

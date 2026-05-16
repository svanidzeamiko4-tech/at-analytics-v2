"""
AI Chat Assistant for AT Analytics distribution dashboard.
Uses Claude API with SQLite context for smart recommendations.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import streamlit as st

from data_loader import resolve_db_path

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


def _get_store_context(db_path: Path, store_query: str) -> str:
    """Get relevant store data for AI context."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT s.id, s.name, s.address,
               COUNT(i.id) as invoice_count,
               ROUND(AVG(i.total), 2) as avg_invoice,
               MAX(i.invoice_date) as last_visit
        FROM stores s
        LEFT JOIN invoices i ON i.store_id = s.id
        WHERE s.name LIKE ? OR s.address LIKE ?
        GROUP BY s.id
        ORDER BY last_visit DESC
        LIMIT 5
        """,
        (f"%{store_query}%", f"%{store_query}%"),
    )
    stores = cur.fetchall()

    if not stores:
        conn.close()
        return "მაღაზია ვერ მოიძებნა."

    context_parts = []
    for store in stores:
        sid, name, addr, inv_count, avg_inv, last_visit = store

        cur.execute(
            """
            SELECT
                COALESCE(p.name, ii.description) as product,
                ROUND(SUM(ii.quantity), 1) as total_qty,
                ROUND(AVG(ii.quantity), 1) as avg_qty_per_visit,
                ROUND(SUM(ii.line_total), 2) as total_gel
            FROM invoice_items ii
            JOIN invoices i ON i.id = ii.invoice_id
            LEFT JOIN products p ON p.id = ii.product_id
            WHERE i.store_id = ?
            GROUP BY COALESCE(p.name, ii.description)
            ORDER BY total_qty DESC
            LIMIT 10
            """,
            (sid,),
        )
        products = cur.fetchall()

        cur.execute(
            """
            SELECT invoice_date, total
            FROM invoices
            WHERE store_id = ?
            ORDER BY invoice_date DESC
            LIMIT 5
            """,
            (sid,),
        )
        recent = cur.fetchall()

        prod_text = "\n".join(
            [
                f"  - {p[0]}: სულ {p[1]} ცალი, საშ. {p[2]}/ვიზიტი, {p[3]} GEL"
                for p in products
            ]
        )
        recent_text = "\n".join([f"  - {r[0]}: {r[1]} GEL" for r in recent])

        context_parts.append(
            f"""
მაღაზია: {name}
მისამართი: {addr}
ვიზიტების რაოდენობა: {inv_count}
საშუალო ინვოისი: {avg_inv} GEL
ბოლო ვიზიტი: {last_visit}

ტოპ პროდუქტები:
{prod_text}

ბოლო ვიზიტები:
{recent_text}
"""
        )

    conn.close()
    return "\n---\n".join(context_parts)


def _get_general_context(db_path: Path) -> str:
    """Get general analytics context."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM stores WHERE name != '(უცნობი მყიდველი)'")
    store_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*), ROUND(SUM(total), 2) FROM invoices")
    inv_count, total_rev = cur.fetchone()

    cur.execute(
        """
        SELECT COALESCE(p.name, ii.description),
               ROUND(SUM(ii.quantity), 1) as qty
        FROM invoice_items ii
        LEFT JOIN products p ON p.id = ii.product_id
        GROUP BY COALESCE(p.name, ii.description)
        ORDER BY qty DESC
        LIMIT 5
        """
    )
    top_products = cur.fetchall()

    conn.close()

    top_prod_text = "\n".join([f"  - {p[0]}: {p[1]} ცალი" for p in top_products])

    return f"""
AT Analytics — დისტრიბუციის სისტემა
მაღაზიების რაოდენობა: {store_count}
სულ ინვოისები: {inv_count}
სულ შემოსავალი: {total_rev} GEL

ტოპ 5 პროდუქტი (რაოდენობით):
{top_prod_text}
"""


def render_ai_chat(*, compact: bool = False) -> None:
    """Render AI chat interface in Streamlit."""
    if not compact:
        st.markdown("### 🤖 AI დისტრიბუციის ასისტენტი")
        st.caption("კითხვები მარაგების, გაყიდვების და მარშრუტების შესახებ")

    db_path = resolve_db_path()

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if prompt := st.chat_input("მაგ: ნიკორა #464-ში ხვალ ვაპირებ მისვლას, რა შევიტანო?"):
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        general_ctx = _get_general_context(db_path)

        store_ctx = ""
        for kw in _STORE_KEYWORDS:
            if kw in prompt:
                store_ctx = _get_store_context(db_path, kw)
                break

        hash_match = re.search(r"#(\d+)", prompt)
        if hash_match and not store_ctx:
            store_ctx = _get_store_context(db_path, f"#{hash_match.group(1)}")

        store_block = (
            f"კონკრეტული მაღაზიის მონაცემები:\n{store_ctx}"
            if store_ctx
            else ""
        )

        system_prompt = f"""შენ ხარ AT Analytics-ის AI ასისტენტი — პური და საკვები პროდუქტების დისტრიბუციის კომპანიის ჭკვიანი მრჩეველი.

შენი ამოცანაა:
1. დისტრიბუტორებს დაეხმარო მარაგების ოპტიმალურ დაგეგმვაში
2. კონკრეტული მაღაზიის გაყიდვების ისტორიაზე დაყრდნობით რჩევა გასცე
3. ქართულად ისაუბრო, მოკლედ და კონკრეტულად
4. კონკრეტული რაოდენობები და სახეობები დაასახელო

მონაცემთა ბაზის კონტექსტი:
{general_ctx}

{store_block}

თუ მაღაზია ვერ მოიძებნა ბაზაში, თქვი და ზოგადი რჩევა გასცე.
პასუხი იყოს პრაქტიკული, კონკრეტული და მოკლე (max 200 სიტყვა)."""

        import anthropic

        client = anthropic.Anthropic()
        messages_for_api = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.chat_messages
        ]

        with st.chat_message("assistant"):
            with st.spinner("ვფიქრობ..."):
                try:
                    response = client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=1000,
                        system=system_prompt,
                        messages=messages_for_api,
                    )
                    answer = response.content[0].text
                    st.write(answer)
                    st.session_state.chat_messages.append(
                        {"role": "assistant", "content": answer}
                    )
                except Exception as e:
                    st.error(f"შეცდომა: {e}")

    if st.button("🗑️ ჩატის გასუფთავება", key="clear_chat"):
        st.session_state.chat_messages = []
        st.rerun()


def render_floating_ai_chat() -> None:
    """Fixed bottom-right FAB; chat panel opens as overlay when toggled."""
    if "show_ai_chat" not in st.session_state:
        st.session_state.show_ai_chat = False

    if st.button("💬", key="fab_chat_toggle", help="AI დისტრიბუციის ასისტენტი"):
        st.session_state.show_ai_chat = not st.session_state.show_ai_chat
        st.rerun()

    if st.session_state.show_ai_chat:
        with st.container(key="ai_chat_panel"):
            _, _close = st.columns([8, 1])
            with _close:
                if st.button("✕", key="fab_chat_close", help="დახურვა"):
                    st.session_state.show_ai_chat = False
                    st.rerun()
            render_ai_chat(compact=True)

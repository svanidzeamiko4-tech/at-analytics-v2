"""
Manager Admin Panel — user and store assignment management.
Accessible only to manager role.
"""

from __future__ import annotations

import sqlite3

import streamlit as st

from auth.auth import get_role
from auth.users import (
    assign_store,
    change_password,
    create_user,
    delete_user,
    get_all_users,
    get_user_stores,
    remove_store,
)
from data_loader import resolve_db_path
from ui_theme import (
    BG,
    BORDER,
    CARD,
    FONT_BODY,
    GOOGLE_FONTS_URL,
    MUTED,
    PRIMARY,
    RADIUS,
    TEXT,
    _logo_b64,
    apply_watermark,
)


def _admin_css() -> str:
    return f"""
    @import url('{GOOGLE_FONTS_URL}');
    .stApp {{ background-color: {BG} !important; color: {TEXT} !important; font-family: {FONT_BODY}; }}
    [data-testid="stSidebar"] {{ background-color: {CARD} !important; border-right: 1px solid {BORDER}; }}
    .stTabs [data-baseweb="tab-list"] {{ background-color: {CARD} !important; border: 1px solid {BORDER}; border-radius: 12px; }}
    .stTabs [aria-selected="true"] {{ color: {PRIMARY} !important; }}
    .stExpander {{ background-color: {CARD} !important; border: 1px solid {BORDER} !important; border-radius: {RADIUS} !important; }}
    .stTextInput > div > div > input, .stSelectbox > div > div {{
        background: {CARD} !important;
        color: {TEXT} !important;
        border: 1px solid {BORDER} !important;
        border-radius: 12px !important;
    }}
    h1, h2, h3, p, label {{ color: {TEXT} !important; }}
    """


def _get_all_stores() -> list[tuple[int, str, str]]:
    """Returns [(store_id, name, address)]."""
    db_path = resolve_db_path()
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT s.id, s.name, COALESCE(s.address, '')
            FROM stores s
            WHERE s.name != '(უცნობი მყიდველი)'
            ORDER BY s.name
            """
        )
        return [(int(r[0]), str(r[1]), str(r[2])) for r in cur.fetchall()]
    finally:
        conn.close()


def render() -> None:
    if get_role() != "manager":
        st.error("ადმინ პანელზე წვდომა მხოლოდ მენეჯერს აქვს.")
        return

    st.markdown(f"<style>{_admin_css()}</style>", unsafe_allow_html=True)
    apply_watermark(_logo_b64(), opacity=0.04)

    st.markdown("## ⚙️ ადმინისტრირება")
    st.caption("მომხმარებლების და მაღაზიების მართვა")

    tab1, tab2 = st.tabs(["👥 მომხმარებლები", "🏪 მაღაზიების მიბმა"])

    with tab1:
        st.markdown("### მომხმარებლის შექმნა")
        with st.form("create_user_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                new_username = st.text_input("მომხმარებელი")
            with col2:
                new_password = st.text_input("პაროლი", type="password")
            with col3:
                new_role = st.selectbox("როლი", ["distributor", "manager"])
            if st.form_submit_button("➕ შექმნა", use_container_width=True):
                if new_username and new_password:
                    ok, msg = create_user(new_username, new_password, new_role)
                    if ok:
                        st.success(f"✅ მომხმარებელი '{new_username}' შეიქმნა")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")
                else:
                    st.warning("შეავსეთ ყველა ველი")

        st.markdown("### არსებული მომხმარებლები")
        users = get_all_users()
        for user in users:
            uid, uname, urole = user["id"], user["username"], user["role"]
            with st.expander(f"{'👑' if urole == 'manager' else '🚚'} {uname} — {urole}"):
                col1, col2 = st.columns(2)
                with col1:
                    new_pw = st.text_input(
                        "ახალი პაროლი",
                        type="password",
                        key=f"pw_{uid}",
                    )
                    if st.button("🔑 პაროლის შეცვლა", key=f"chpw_{uid}"):
                        if new_pw:
                            change_password(uid, new_pw)
                            st.success("პაროლი შეიცვალა")
                        else:
                            st.warning("შეიყვანეთ ახალი პაროლი")
                with col2:
                    if urole != "manager":
                        if st.button(
                            "🗑️ წაშლა",
                            key=f"del_{uid}",
                            type="secondary",
                        ):
                            delete_user(uid)
                            st.success(f"'{uname}' წაიშალა")
                            st.rerun()

    with tab2:
        st.markdown("### მაღაზიების მიბმა დისტრიბუტორზე")
        all_stores = _get_all_stores()
        distributors = [u for u in get_all_users() if u["role"] == "distributor"]
        if not distributors:
            st.info("დისტრიბუტორები არ არის. ჯერ შექმენით.")
            return

        selected_dist = st.selectbox(
            "დისტრიბუტორი",
            options=[u["username"] for u in distributors],
            key="admin_dist_select",
        )
        dist_user = next(u for u in distributors if u["username"] == selected_dist)
        dist_id = dist_user["id"]
        assigned_ids = set(get_user_stores(dist_id))

        st.markdown(f"**{selected_dist}**-ის მაღაზიები:")

        search = st.text_input(
            "🔍 მაღაზიის ძებნა",
            key="store_search",
            placeholder="ნიკორა, ორი ნაბიჯი...",
        )
        filtered = [
            s
            for s in all_stores
            if not search
            or search.lower() in s[1].lower()
            or search.lower() in s[2].lower()
        ]

        for sid, sname, saddr in filtered:
            is_assigned = sid in assigned_ids
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                badge = "✅" if is_assigned else "⬜"
                st.markdown(f"{badge} **{sname}**")
            with col2:
                addr = (saddr[:40] + "…") if len(saddr) > 40 else saddr
                st.caption(addr or "—")
            with col3:
                if is_assigned:
                    if st.button(
                        "მოხსნა",
                        key=f"rem_{dist_id}_{sid}",
                        type="secondary",
                    ):
                        remove_store(dist_id, sid)
                        st.rerun()
                else:
                    if st.button("მიბმა", key=f"asgn_{dist_id}_{sid}"):
                        assign_store(dist_id, sid)
                        st.rerun()

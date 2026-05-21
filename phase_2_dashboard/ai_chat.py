"""
AI Chat Assistant — Haiku, prompt caching, streaming (Phase 3).

Uses ``data_loader`` via ``ai.context_builder`` only (no direct SQL).
"""

from __future__ import annotations

import streamlit as st

from ai.claude_client import build_messages, stream_assistant_reply
from ai.context_builder import build_session_context
from auth.auth import get_current_user, get_session_id, is_authenticated


def render_ai_chat(*, compact: bool = False) -> None:
    """Render AI chat interface in Streamlit."""
    if not compact:
        st.markdown("### 🤖 AI დისტრიბუციის ასისტენტი")
        st.caption("კითხვები მარაგების, გაყიდვების და მარშრუტების შესახებ")

    if not is_authenticated():
        st.warning("ჩატის გამოსაყენებლად შედით სისტემაში.")
        return

    user = get_current_user()
    if user is None:
        st.warning("სესია ვერ მოიძებნა.")
        return

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if prompt := st.chat_input("მაგ: ნიკორა #464-ში ხვალ ვაპირებ მისვლას, რა შევიტანო?"):
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        session_ctx = build_session_context(prompt)

        messages_for_api = build_messages(
            st.session_state.chat_messages,
            prompt,
            session_ctx,
        )

        with st.chat_message("assistant"):
            try:
                uid = int(user["id"])
                sid = get_session_id()
                answer = st.write_stream(
                    lambda: stream_assistant_reply(
                        messages_for_api,
                        user_id=uid,
                        session_id=sid,
                    )
                )
                st.session_state.chat_messages.append(
                    {"role": "assistant", "content": answer or ""}
                )
            except Exception as exc:
                st.error(f"შეცდომა: {exc}")

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

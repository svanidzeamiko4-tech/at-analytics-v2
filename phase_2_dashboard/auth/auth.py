"""
Streamlit session + signed token (HMAC) + server-side session_id validation (Phase 4).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

import streamlit as st
from streamlit_cookies_manager import EncryptedCookieManager

from auth.sessions import create_session, revoke_session, validate_session
from auth.users import authenticate, init_auth_db

_SESSION_USER = "auth_user"
_SESSION_TOKEN = "auth_token"
_SESSION_ID = "auth_session_id"
_TOKEN_TTL_SEC = 60 * 60 * 12  # 12 hours

_COOKIE_NAME = "at_auth_token"
_COOKIE_PASSWORD = os.environ.get("AT_AUTH_SECRET", "at-analytics-dev-secret-change-me")


def _get_cookies():
    if "at_cookie_manager" not in st.session_state:
        cookies = EncryptedCookieManager(prefix="at_", password=_COOKIE_PASSWORD)
        st.session_state["at_cookie_manager"] = cookies
    cookies = st.session_state["at_cookie_manager"]
    if not cookies.ready():
        st.stop()
    return cookies


def _secret() -> bytes:
    return os.environ.get("AT_AUTH_SECRET", "at-analytics-dev-secret-change-me").encode(
        "utf-8"
    )


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def create_token(user: dict[str, Any], session_id: str) -> str:
    payload = {
        "sub": user["id"],
        "sid": session_id,
        "username": user["username"],
        "role": user["role"],
        "display_name": user["display_name"],
        "store_ids": user.get("store_ids") or [],
        "exp": int(time.time()) + _TOKEN_TTL_SEC,
    }
    body = _b64url_encode(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    sig = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64url_encode(sig)}"


def verify_token(token: str) -> dict[str, Any] | None:
    try:
        body, sig = token.rsplit(".", 1)
        expected = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(_b64url_encode(expected), sig):
            return None
        payload = json.loads(_b64url_decode(body).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        sid = payload.get("sid")
        uid = int(payload.get("sub", 0))
        if not sid or not validate_session(str(sid), uid):
            return None
        return payload
    except (ValueError, json.JSONDecodeError, OSError, TypeError):
        return None


def login(username: str, password: str) -> bool:
    init_auth_db()
    user = authenticate(username, password)
    if user is None:
        return False
    session_id = create_session(int(user["id"]))
    st.session_state[_SESSION_USER] = user
    st.session_state[_SESSION_ID] = session_id
    st.session_state[_SESSION_TOKEN] = create_token(user, session_id)
    cookies = _get_cookies()
    cookies[_COOKIE_NAME] = st.session_state[_SESSION_TOKEN]
    cookies.save()
    return True


def logout() -> None:
    revoke_session(st.session_state.get(_SESSION_ID))
    st.session_state.pop(_SESSION_USER, None)
    st.session_state.pop(_SESSION_TOKEN, None)
    st.session_state.pop(_SESSION_ID, None)
    try:
        cookies = _get_cookies()
        cookies[_COOKIE_NAME] = ""
        cookies.save()
    except Exception:
        pass


def restore_session() -> None:
    """Rehydrate user from signed token + live session row."""
    if _SESSION_USER in st.session_state:
        sid = st.session_state.get(_SESSION_ID)
        user = st.session_state.get(_SESSION_USER)
        if user and sid and validate_session(str(sid), int(user["id"])):
            return
        logout()
        return

    token = st.session_state.get(_SESSION_TOKEN)
    if not token:
        try:
            cookies = _get_cookies()
            token = cookies.get(_COOKIE_NAME, "")
            if token:
                st.session_state[_SESSION_TOKEN] = token
        except Exception:
            pass
    if not token:
        return
    payload = verify_token(str(token))
    if payload is None:
        logout()
        return
    st.session_state[_SESSION_ID] = payload["sid"]
    st.session_state[_SESSION_USER] = {
        "id": int(payload["sub"]),
        "username": payload["username"],
        "role": payload["role"],
        "display_name": payload.get("display_name") or payload["username"],
        "store_ids": list(payload.get("store_ids") or []),
    }


def is_authenticated() -> bool:
    restore_session()
    return _SESSION_USER in st.session_state


def get_current_user() -> dict[str, Any] | None:
    restore_session()
    return st.session_state.get(_SESSION_USER)


def get_session_id() -> str | None:
    restore_session()
    sid = st.session_state.get(_SESSION_ID)
    return str(sid) if sid else None


def get_role() -> str | None:
    user = get_current_user()
    return None if user is None else str(user.get("role"))


def get_allowed_store_ids() -> frozenset[int] | None:
    """
    ``None`` = manager (all stores).
    Empty frozenset = distributor with no assignments.
    """
    user = get_current_user()
    if user is None:
        return frozenset()
    if user.get("role") == "manager":
        return None
    return frozenset(int(x) for x in (user.get("store_ids") or []))

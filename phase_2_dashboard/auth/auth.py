"""
Streamlit session + signed token (HMAC JWT-style, stdlib only).
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

from auth.users import authenticate, init_auth_db

_SESSION_USER = "auth_user"
_SESSION_TOKEN = "auth_token"
_TOKEN_TTL_SEC = 60 * 60 * 12  # 12 hours


def _secret() -> bytes:
    return os.environ.get("AT_AUTH_SECRET", "at-analytics-dev-secret-change-me").encode(
        "utf-8"
    )


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def create_token(user: dict[str, Any]) -> str:
    payload = {
        "sub": user["id"],
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
        return payload
    except (ValueError, json.JSONDecodeError, OSError):
        return None


def login(username: str, password: str) -> bool:
    init_auth_db()
    user = authenticate(username, password)
    if user is None:
        return False
    st.session_state[_SESSION_USER] = user
    st.session_state[_SESSION_TOKEN] = create_token(user)
    return True


def logout() -> None:
    st.session_state.pop(_SESSION_USER, None)
    st.session_state.pop(_SESSION_TOKEN, None)


def restore_session() -> None:
    """Rehydrate user from signed token if present."""
    if _SESSION_USER in st.session_state:
        return
    token = st.session_state.get(_SESSION_TOKEN)
    if not token:
        return
    payload = verify_token(str(token))
    if payload is None:
        logout()
        return
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

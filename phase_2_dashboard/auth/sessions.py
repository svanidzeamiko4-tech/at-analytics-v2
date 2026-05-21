"""
Server-side session registry (Phase 4) — prevents token replay after logout.

Schema for ``sessions`` is created here only. User tables are initialized by
``auth.users.init_auth_db()`` first (no call back into init_auth_db).
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from auth.users import _connect

_SESSION_DDL = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
"""

_TTL_HOURS = 12
_schema_ready = False


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def ensure_sessions_schema() -> None:
    """Create ``sessions`` table only. Requires ``users`` table to exist already."""
    global _schema_ready
    if _schema_ready:
        return
    with _connect() as conn:
        conn.executescript(_SESSION_DDL)
        conn.commit()
    _schema_ready = True


def create_session(user_id: int, *, ttl_hours: int = _TTL_HOURS) -> str:
    ensure_sessions_schema()
    session_id = secrets.token_urlsafe(32)
    now = _utcnow()
    expires = now + timedelta(hours=ttl_hours)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO sessions (session_id, user_id, created_at, expires_at, revoked)
            VALUES (?, ?, ?, ?, 0)
            """,
            (session_id, int(user_id), _fmt(now), _fmt(expires)),
        )
        conn.commit()
    return session_id


def validate_session(session_id: str, user_id: int) -> bool:
    if not session_id:
        return False
    ensure_sessions_schema()
    now_s = _fmt(_utcnow())
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM sessions
            WHERE session_id = ? AND user_id = ? AND revoked = 0
              AND expires_at > ?
            """,
            (session_id, int(user_id), now_s),
        ).fetchone()
    return row is not None


def revoke_session(session_id: str | None) -> None:
    if not session_id:
        return
    ensure_sessions_schema()
    with _connect() as conn:
        conn.execute(
            "UPDATE sessions SET revoked = 1 WHERE session_id = ?",
            (session_id,),
        )
        conn.commit()


def revoke_all_for_user(user_id: int) -> None:
    ensure_sessions_schema()
    with _connect() as conn:
        conn.execute(
            "UPDATE sessions SET revoked = 1 WHERE user_id = ?",
            (int(user_id),),
        )
        conn.commit()

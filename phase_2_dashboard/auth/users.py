"""
Application users (manager / distributor) and store assignments.

SQLite file: ``phase_2_dashboard/auth/at_auth.db`` (separate from ``amiko_v3.db``).
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from auth.passwords import hash_password, needs_rehash, verify_password

AUTH_DB_NAME = "at_auth.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('manager', 'distributor')),
    display_name TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_stores (
    user_id INTEGER NOT NULL,
    store_id INTEGER NOT NULL,
    PRIMARY KEY (user_id, store_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_stores_store ON user_stores(store_id);
"""


def get_auth_db_path() -> Path:
    return Path(__file__).resolve().parent / AUTH_DB_NAME


def _connect() -> sqlite3.Connection:
    path = get_auth_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_auth_db(seed_if_empty: bool = True) -> Path:
    """Create users schema, then sessions schema; optionally seed defaults."""
    path = get_auth_db_path()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()

    from auth.sessions import ensure_sessions_schema

    ensure_sessions_schema()

    if seed_if_empty:
        with _connect() as conn:
            n = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            if n == 0:
                _seed_defaults(conn)
    return path


def _seed_defaults(conn: sqlite3.Connection) -> None:
    mgr_pass = os.environ.get("AT_MANAGER_PASSWORD", "manager")
    dist_pass = os.environ.get("AT_DISTRIBUTOR_PASSWORD", "distributor")
    mgr_id = _insert_user_conn(
        conn, "manager", mgr_pass, "manager", "მენეჯერი"
    )
    dist_id = _insert_user_conn(
        conn, "distributor", dist_pass, "distributor", "დისტრიბუტორი"
    )
    analytics_db = Path(__file__).resolve().parents[2] / "amiko_v3.db"
    if analytics_db.is_file():
        cur = conn.cursor()
        aconn = sqlite3.connect(analytics_db)
        try:
            rows = aconn.execute(
                """
                SELECT id FROM stores
                WHERE name != '(უცნობი მყიდველი)'
                ORDER BY id
                LIMIT 8
                """
            ).fetchall()
            for (store_id,) in rows:
                cur.execute(
                    "INSERT OR IGNORE INTO user_stores (user_id, store_id) VALUES (?, ?)",
                    (dist_id, store_id),
                )
        finally:
            aconn.close()
    conn.commit()
    _ = mgr_id


def _insert_user_conn(
    conn: sqlite3.Connection,
    username: str,
    password: str,
    role: str,
    display_name: str | None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO users (username, password_hash, role, display_name)
        VALUES (?, ?, ?, ?)
        """,
        (username.strip(), hash_password(password), role, display_name),
    )
    return int(cur.lastrowid)


def authenticate(username: str, password: str) -> dict[str, Any] | None:
    """Return user dict or None."""
    init_auth_db(seed_if_empty=False)
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, username, password_hash, role, display_name, active
            FROM users
            WHERE username = ? COLLATE NOCASE
            """,
            (username.strip(),),
        ).fetchone()
        if row is None or not row["active"]:
            return None
        stored_hash = row["password_hash"]
        if not verify_password(password, stored_hash):
            return None
        if needs_rehash(stored_hash):
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (hash_password(password), int(row["id"])),
            )
            conn.commit()
        store_ids = _store_ids_for_user(conn, int(row["id"]), row["role"])
        return {
            "id": int(row["id"]),
            "username": row["username"],
            "role": row["role"],
            "display_name": row["display_name"] or row["username"],
            "store_ids": store_ids,
        }


def _store_ids_for_user(
    conn: sqlite3.Connection, user_id: int, role: str
) -> list[int]:
    if role == "manager":
        return []
    rows = conn.execute(
        "SELECT store_id FROM user_stores WHERE user_id = ? ORDER BY store_id",
        (user_id,),
    ).fetchall()
    return [int(r["store_id"]) for r in rows]


def set_user_stores(user_id: int, store_ids: list[int]) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM user_stores WHERE user_id = ?", (user_id,))
        for sid in store_ids:
            conn.execute(
                "INSERT OR IGNORE INTO user_stores (user_id, store_id) VALUES (?, ?)",
                (user_id, int(sid)),
            )
        conn.commit()


def get_all_users() -> list[dict[str, Any]]:
    init_auth_db(seed_if_empty=False)
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, username, role FROM users ORDER BY role, username"
        ).fetchall()
    return [{"id": int(r["id"]), "username": r["username"], "role": r["role"]} for r in rows]


def create_user(username: str, password: str, role: str) -> tuple[bool, str]:
    init_auth_db(seed_if_empty=False)
    if role not in ("manager", "distributor"):
        return False, "არასწორი როლი"
    with _connect() as conn:
        try:
            conn.execute(
                """
                INSERT INTO users (username, password_hash, role)
                VALUES (?, ?, ?)
                """,
                (username.strip(), hash_password(password), role),
            )
            conn.commit()
            return True, "ok"
        except sqlite3.IntegrityError:
            return False, "მომხმარებელი უკვე არსებობს"


def delete_user(user_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM user_stores WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()


def change_password(user_id: int, new_password: str) -> None:
    from auth.sessions import revoke_all_for_user

    with _connect() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(new_password), user_id),
        )
        conn.commit()
    revoke_all_for_user(user_id)


def get_user_stores(user_id: int) -> list[int]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT store_id FROM user_stores WHERE user_id = ?", (user_id,)
        ).fetchall()
    return [int(r["store_id"]) for r in rows]


def assign_store(user_id: int, store_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO user_stores (user_id, store_id) VALUES (?, ?)",
            (user_id, store_id),
        )
        conn.commit()


def remove_store(user_id: int, store_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            "DELETE FROM user_stores WHERE user_id = ? AND store_id = ?",
            (user_id, store_id),
        )
        conn.commit()

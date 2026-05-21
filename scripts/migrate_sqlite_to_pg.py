"""
One-time migration: SQLite auth (at_auth.db) → PostgreSQL auth.users.

Reads users from phase_2_dashboard/auth/at_auth.db, creates auth tables in
PostgreSQL if missing, inserts users that are not already present (by username).

Usage (from repo root):
  pip install sqlalchemy psycopg2-binary
  set USE_POSTGRES=true
  set PYTHONPATH=phase_2_dashboard
  python scripts/migrate_sqlite_to_pg.py

DATABASE_URL: use postgresql+psycopg2://... (psycopg2-binary) or postgresql+psycopg://... (psycopg v3).
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_PKG = _ROOT / "phase_2_dashboard"
_DEFAULT_AUTH_SQLITE = _PKG / "auth" / "at_auth.db"

if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from core.config import get_settings
from database.base import Base
from database.models.auth import User, UserStore


def _sqlite_path() -> Path:
    settings = get_settings()
    path = settings.auth_db_path
    if not path.is_absolute():
        path = _ROOT / path
    path = path.resolve()
    if path.is_file():
        return path
    if _DEFAULT_AUTH_SQLITE.is_file():
        return _DEFAULT_AUTH_SQLITE
    return path


def _database_url_for_engine() -> str:
    """Prefer explicit driver; fall back psycopg → psycopg2 for psycopg2-binary installs."""
    url = get_settings().database_url.strip()
    if url.startswith("postgresql://") and "+" not in url.split("://", 1)[0]:
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def _pg_engine() -> Engine:
    settings = get_settings()
    if not settings.use_postgres:
        raise SystemExit("Set USE_POSTGRES=true in .env before running this script.")
    url = _database_url_for_engine()
    try:
        return create_engine(url)
    except Exception:
        if "postgresql+psycopg://" in url:
            return create_engine(
                url.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
            )
        raise


def ensure_auth_schema(engine: Engine) -> None:
    """Create auth schema and tables (users, user_stores) if they do not exist."""
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS auth"))
    Base.metadata.create_all(
        engine,
        tables=[User.__table__, UserStore.__table__],
        checkfirst=True,
    )
    print("PostgreSQL auth schema ready (auth.users, auth.user_stores).")


def _load_store_ids(sqlite_conn: sqlite3.Connection, user_id: int) -> list[int]:
    rows = sqlite_conn.execute(
        "SELECT store_id FROM user_stores WHERE user_id = ? ORDER BY store_id",
        (user_id,),
    ).fetchall()
    return [int(r[0]) for r in rows]


def _username_exists(engine: Engine, username: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT 1 FROM auth.users
                WHERE LOWER(username) = LOWER(:username)
                LIMIT 1
                """
            ),
            {"username": username},
        ).fetchone()
    return row is not None


def migrate_users() -> int:
    sqlite_path = _sqlite_path()
    if not sqlite_path.is_file():
        raise FileNotFoundError(f"SQLite auth database not found: {sqlite_path}")

    engine = _pg_engine()
    ensure_auth_schema(engine)

    print(f"SQLite source: {sqlite_path}")
    print(f"PostgreSQL target: {get_settings().database_url.split('@')[-1]}")

    migrated = 0
    skipped = 0

    with sqlite3.connect(sqlite_path) as sqlite_conn:
        sqlite_conn.row_factory = sqlite3.Row
        users = sqlite_conn.execute(
            """
            SELECT id, username, password_hash, role, display_name, active, created_at
            FROM users
            ORDER BY id
            """
        ).fetchall()

        print(f"Found {len(users)} user(s) in SQLite.")

        for row in users:
            user_id = int(row["id"])
            username = str(row["username"]).strip()
            store_ids = _load_store_ids(sqlite_conn, user_id)
            store_ids_json = json.dumps(store_ids)

            if _username_exists(engine, username):
                print(f"  skip '{username}' (already in PostgreSQL)")
                skipped += 1
                continue

            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO auth.users (
                            id, username, password_hash, role,
                            display_name, active, created_at
                        ) VALUES (
                            :id, :username, :password_hash, :role,
                            :display_name, :active, :created_at
                        )
                        """
                    ),
                    {
                        "id": user_id,
                        "username": username,
                        "password_hash": row["password_hash"],
                        "role": row["role"],
                        "display_name": row["display_name"],
                        "active": int(row["active"]),
                        "created_at": row["created_at"],
                    },
                )

                for store_id in store_ids:
                    conn.execute(
                        text(
                            """
                            INSERT INTO auth.user_stores (user_id, store_id)
                            VALUES (:user_id, :store_id)
                            ON CONFLICT (user_id, store_id) DO NOTHING
                            """
                        ),
                        {"user_id": user_id, "store_id": store_id},
                    )

            role = row["role"]
            print(
                f"  + '{username}' ({role}) store_ids={store_ids_json}"
            )
            migrated += 1

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                SELECT setval(
                    pg_get_serial_sequence('auth.users', 'id'),
                    COALESCE((SELECT MAX(id) FROM auth.users), 1),
                    (SELECT MAX(id) IS NOT NULL FROM auth.users)
                )
                """
            )
        )

    print(f"Migrated {migrated} users successfully.")
    if skipped:
        print(f"Skipped {skipped} user(s) (duplicate username).")
    return migrated


def main() -> None:
    try:
        migrate_users()
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except Exception as exc:
        print(f"Migration failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()

"""
Read-only analytics DB adapter (Phase 1b).

``data_loader`` calls ``open_analytics_readonly()`` — it does not branch on SQLite vs Postgres.

**Current phase:** ``USE_POSTGRES=false`` → always ``SqliteAnalyticsBackend`` (amiko_v3.db).
PostgreSQL backend is deferred; see docs/LOCAL_SQLITE_ARCHITECTURE.md.
"""

from __future__ import annotations

import re
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Iterator

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from core.config import get_settings

_ANALYTICS_SCHEMA = "analytics"
_TABLES = frozenset(
    {
        "stores",
        "products",
        "invoices",
        "invoice_items",
        "product_merge_rules",
    }
)
_QUALIFY_RX = re.compile(
    r"\b(?<!\.)(?P<t>" + "|".join(sorted(_TABLES, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
_PRAGMA_TABLE_INFO_RX = re.compile(
    r"^\s*PRAGMA\s+table_info\s*\(\s*(?P<table>[\w]+)\s*\)\s*;?\s*$",
    re.IGNORECASE,
)


class _CursorResult:
    """Minimal DB-API cursor (``fetchall`` / ``description``) for PRAGMA emulation."""

    def __init__(self, rows: list[tuple], columns: tuple[str, ...]) -> None:
        self._rows = rows
        self.description = [(c,) for c in columns]

    def fetchall(self) -> list[tuple]:
        return self._rows


class AnalyticsReadonlyBackend(ABC):
    """Duck-typed read-only connection used by ``pandas.read_sql_query`` and ``execute``."""

    @abstractmethod
    def execute(self, sql: str, params: tuple | dict | None = None) -> _CursorResult | Any:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError

    def __enter__(self) -> AnalyticsReadonlyBackend:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class SqliteAnalyticsBackend(AnalyticsReadonlyBackend):
    def __init__(self, db_path: Path) -> None:
        if not db_path.is_file():
            raise FileNotFoundError(f"Database not found: {db_path}")
        uri = db_path.resolve().as_uri() + "?mode=ro"
        self._conn = sqlite3.connect(uri, uri=True)
        self._conn.row_factory = sqlite3.Row

    def execute(self, sql: str, params: tuple | dict | None = None) -> sqlite3.Cursor:
        if params:
            return self._conn.execute(sql, params)
        return self._conn.execute(sql)

    def close(self) -> None:
        self._conn.close()

    @property
    def raw_connection(self) -> sqlite3.Connection:
        return self._conn


class PostgresAnalyticsBackend(AnalyticsReadonlyBackend):
    """PostgreSQL ``analytics`` schema; SQL/PRAGMA translated at the boundary."""

    def __init__(self) -> None:
        from database.engine import get_engine

        self._engine: Engine = get_engine()
        self._conn: Connection = self._engine.connect()

    def _table_columns(self, table: str) -> list[tuple]:
        q = text(
            """
            SELECT ordinal_position, column_name, data_type, is_nullable, column_default, ''
            FROM information_schema.columns
            WHERE table_schema = :schema AND table_name = :table
            ORDER BY ordinal_position
            """
        )
        rows = self._conn.execute(
            q, {"schema": _ANALYTICS_SCHEMA, "table": table.lower()}
        ).fetchall()
        # SQLite PRAGMA shape: (cid, name, type, notnull, dflt_value, pk)
        out: list[tuple] = []
        for r in rows:
            cid = int(r[0]) - 1
            name = r[1]
            ctype = r[2] or ""
            notnull = 0 if (r[3] or "").upper() == "YES" else 1
            default = r[4]
            out.append((cid, name, ctype, notnull, default, 0))
        return out

    @staticmethod
    def _qualify_sql(sql: str) -> str:
        return _QUALIFY_RX.sub(lambda m: f"{_ANALYTICS_SCHEMA}.{m.group('t')}", sql)

    def execute(self, sql: str, params: tuple | dict | None = None) -> _CursorResult:
        m = _PRAGMA_TABLE_INFO_RX.match(sql.strip())
        if m:
            table = m.group("table")
            rows = self._table_columns(table)
            return _CursorResult(rows, ("cid", "name", "type", "notnull", "dflt_value", "pk"))
        q = self._qualify_sql(sql)
        result = (
            self._conn.execute(text(q), params)
            if params
            else self._conn.execute(text(q))
        )
        return _CursorResult(
            [tuple(row) for row in result.fetchall()],
            tuple(result.keys()),
        )

    def close(self) -> None:
        self._conn.close()

    @property
    def raw_connection(self) -> Connection:
        return self._conn


def _default_sqlite_path() -> Path:
    return get_settings().resolved_analytics_sqlite()


def open_analytics_readonly(db_path: Path | None = None) -> AnalyticsReadonlyBackend:
    """
    Factory used by ``data_loader.connect_readonly``.

    Returns a context-manager-friendly backend; ``pandas.read_sql_query`` accepts
    ``.raw_connection`` on both implementations.
    """
    if get_settings().use_postgres:
        return PostgresAnalyticsBackend()
    path = (db_path or _default_sqlite_path()).resolve()
    return SqliteAnalyticsBackend(path)


def read_sql_query(sql: str, conn: AnalyticsReadonlyBackend) -> pd.DataFrame:
    """Run SELECT via adapter (qualifies table names for Postgres)."""
    if isinstance(conn, PostgresAnalyticsBackend):
        sql = PostgresAnalyticsBackend._qualify_sql(sql)
        return pd.read_sql_query(text(sql), conn.raw_connection)
    return pd.read_sql_query(sql, conn.raw_connection)

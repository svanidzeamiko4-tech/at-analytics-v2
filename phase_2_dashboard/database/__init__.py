"""
PostgreSQL access layer (Phase 1).

Existing dashboards keep using ``data_loader.connect_readonly()`` until
``USE_POSTGRES=true`` and a deliberate Phase 1b switch.
"""

from database.adapter import open_analytics_readonly, read_sql_query
from database.engine import dispose_engine, get_engine
from database.session import get_session

__all__ = [
    "get_engine",
    "get_session",
    "dispose_engine",
    "open_analytics_readonly",
    "read_sql_query",
]

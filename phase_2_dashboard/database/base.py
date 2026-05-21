"""SQLAlchemy declarative base — multi-schema for admin / Telegram extension."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Root ORM base; tables use explicit PostgreSQL schemas."""

    pass

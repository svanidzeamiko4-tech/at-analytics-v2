"""
Auth schema — mirrors ``at_auth.db``; extensible for admin API & Telegram bot.

Future tables (not created in 001): api_tokens, telegram_subscriptions, role_permissions.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base

_SCHEMA = "auth"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('manager', 'distributor')", name="ck_users_role"),
        {"schema": _SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    active: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UserStore(Base):
    __tablename__ = "user_stores"
    __table_args__ = (
        Index("idx_user_stores_store", "store_id"),
        {"schema": _SCHEMA},
    )

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(f"{_SCHEMA}.users.id", ondelete="CASCADE"), primary_key=True
    )
    store_id: Mapped[int] = mapped_column(Integer, primary_key=True)

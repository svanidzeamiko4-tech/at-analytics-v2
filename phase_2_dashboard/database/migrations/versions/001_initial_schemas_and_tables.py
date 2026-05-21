"""Initial PostgreSQL schemas and tables (mirrors SQLite baseline).

Revision ID: 001_initial
Revises:
Create Date: 2026-05-20

Why: Enterprise Phase 1 — multi-schema layout for analytics, auth, integrations, audit.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for schema in ("auth", "analytics", "integrations", "audit"):
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

    from database.models import Base

    bind = op.get_bind()
    Base.metadata.create_all(bind, checkfirst=True)


def downgrade() -> None:
    from database.models import Base

    bind = op.get_bind()
    Base.metadata.drop_all(bind)

    for schema in ("audit", "integrations", "analytics", "auth"):
        op.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")

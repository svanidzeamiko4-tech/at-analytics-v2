"""Add waybills_count to integrations.sync_runs.

Revision ID: 002_sync_runs
Revises: 001_initial
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_sync_runs"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sync_runs",
        sa.Column("waybills_count", sa.Integer(), nullable=True),
        schema="integrations",
    )


def downgrade() -> None:
    op.drop_column("sync_runs", "waybills_count", schema="integrations")

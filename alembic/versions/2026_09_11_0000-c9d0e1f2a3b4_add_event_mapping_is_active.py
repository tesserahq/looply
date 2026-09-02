"""add event mapping is_active

Revision ID: c9d0e1f2a3b4
Revises: b7c8d9e0f1a2
Create Date: 2026-09-11 00:00:00.000000

Adds EventMapping.is_active so an event_type can be paused without soft-
deleting it - unlike delete, disabling doesn't free up event_type for reuse
(no change to the existing partial unique index, which is keyed on
deleted_at, not is_active). Every existing row backfills to true so no
currently-ingesting event_type stops being processed by this deploy. See the
grill-me session on disabling/enabling event mappings.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "event_mappings",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.alter_column("event_mappings", "is_active", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("event_mappings", "is_active")

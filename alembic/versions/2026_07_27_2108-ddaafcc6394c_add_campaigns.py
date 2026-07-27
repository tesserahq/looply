"""add campaigns

Revision ID: ddaafcc6394c
Revises: f6a7b8c9d0e1
Create Date: 2026-07-27 21:08:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "ddaafcc6394c"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "campaigns",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("contact_list_id", sa.UUID(as_uuid=True), nullable=False),
        # project_id/template_id reference Sendly's own domain, not local tables.
        sa.Column("project_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("template_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "template_variables",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("from_email", sa.String(), nullable=True),
        sa.Column("subject", sa.String(), nullable=True),
        sa.Column(
            "tags", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'")
        ),
        sa.Column("batch_id", sa.String(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["contact_list_id"], ["contact_lists.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="CASCADE"),
    )
    # Supports the Celery beat poller's scan for campaigns with status='sending'.
    op.create_index("ix_campaigns_status", "campaigns", ["status"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_campaigns_status", table_name="campaigns")
    op.drop_table("campaigns")

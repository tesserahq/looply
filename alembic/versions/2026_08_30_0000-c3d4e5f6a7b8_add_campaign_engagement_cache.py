"""add campaign engagement cache

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-30 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "campaigns",
        sa.Column("delivered_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "campaigns",
        sa.Column("bounced_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "campaigns",
        sa.Column("complained_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "campaigns",
        sa.Column("opened_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "campaigns",
        sa.Column("clicked_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "campaigns",
        sa.Column("engagement_last_synced_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "campaigns",
        sa.Column("engagement_polling_expires_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "campaign_recipients", sa.Column("opened_at", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "campaign_recipients", sa.Column("clicked_at", sa.DateTime(), nullable=True)
    )
    # Supports poll_campaign_engagement's scan for completed campaigns still
    # inside their polling window.
    op.create_index(
        "ix_campaigns_engagement_polling_expires_at",
        "campaigns",
        ["engagement_polling_expires_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_campaigns_engagement_polling_expires_at", table_name="campaigns")
    op.drop_column("campaign_recipients", "clicked_at")
    op.drop_column("campaign_recipients", "opened_at")
    op.drop_column("campaigns", "engagement_polling_expires_at")
    op.drop_column("campaigns", "engagement_last_synced_at")
    op.drop_column("campaigns", "clicked_count")
    op.drop_column("campaigns", "opened_count")
    op.drop_column("campaigns", "complained_count")
    op.drop_column("campaigns", "bounced_count")
    op.drop_column("campaigns", "delivered_count")

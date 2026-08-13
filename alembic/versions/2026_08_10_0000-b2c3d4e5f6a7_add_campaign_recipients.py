"""add campaign_recipients

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-10 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "campaign_recipients",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "campaign_id",
            "contact_id",
            name="uq_campaign_recipients_campaign_contact",
        ),
    )
    # Supports "which campaigns has this contact received" lookups.
    op.create_index(
        "ix_campaign_recipients_contact_id", "campaign_recipients", ["contact_id"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_campaign_recipients_contact_id", table_name="campaign_recipients")
    op.drop_table("campaign_recipients")

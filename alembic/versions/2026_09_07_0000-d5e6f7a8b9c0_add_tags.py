"""add tags

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-09-07 00:00:00.000000

Normalized Tag entity shared by contacts and campaigns, replacing campaigns'
free-form JSONB tags column (no data migration - existing campaign tags are
dropped, campaigns start fresh with the new model). See docs/prds for the
contact-tags PRD.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tags",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_by_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    # Partial, case-insensitive unique index scoped to active rows only - mirrors
    # custom_field_definitions.name so a soft-deleted tag's name can be reused by
    # a newly auto-created row (see TagRepository.get_or_create_tags).
    op.execute(
        "CREATE UNIQUE INDEX uq_tags_name "
        "ON tags (lower(name)) "
        "WHERE deleted_at IS NULL"
    )

    op.create_table(
        "contact_tags",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("tag_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "contact_id", "tag_id", name="uq_contact_tags_contact_tag"
        ),
    )

    op.create_table(
        "campaign_tags",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("tag_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "campaign_id", "tag_id", name="uq_campaign_tags_campaign_tag"
        ),
    )

    # No data migration - campaigns' existing free-form tags aren't carried over.
    op.drop_column("campaigns", "tags")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "campaigns",
        sa.Column(
            "tags",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.drop_table("campaign_tags")
    op.drop_table("contact_tags")
    op.execute("DROP INDEX uq_tags_name")
    op.drop_table("tags")

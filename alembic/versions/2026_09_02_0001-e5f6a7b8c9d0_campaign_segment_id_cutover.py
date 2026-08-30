"""campaign segment_id cutover

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-02 00:01:00.000000

A campaign's audience is now always "resolve this segment" instead of "send
to this one contact list" - see docs/prds/0001-campaign-segments.md's Phase
2. This is a clean breaking schema change: there is no production data to
preserve, so existing campaign rows (and their recipients) are dropped
rather than migrated. Campaign.contact_list_id is replaced by the required
Campaign.segment_id.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # No production data to preserve - drop existing campaign rows (and
    # their recipients, via the FK's ON DELETE CASCADE) rather than migrate.
    op.execute("TRUNCATE TABLE campaign_recipients, campaigns CASCADE")

    op.drop_constraint(
        "campaigns_contact_list_id_fkey", "campaigns", type_="foreignkey"
    )
    op.drop_column("campaigns", "contact_list_id")
    op.add_column("campaigns", sa.Column("segment_id", sa.UUID(as_uuid=True), nullable=False))
    op.create_foreign_key(
        "campaigns_segment_id_fkey",
        "campaigns",
        "segments",
        ["segment_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("TRUNCATE TABLE campaign_recipients, campaigns CASCADE")

    op.drop_constraint("campaigns_segment_id_fkey", "campaigns", type_="foreignkey")
    op.drop_column("campaigns", "segment_id")
    op.add_column(
        "campaigns", sa.Column("contact_list_id", sa.UUID(as_uuid=True), nullable=False)
    )
    op.create_foreign_key(
        "campaigns_contact_list_id_fkey",
        "campaigns",
        "contact_lists",
        ["contact_list_id"],
        ["id"],
        ondelete="CASCADE",
    )

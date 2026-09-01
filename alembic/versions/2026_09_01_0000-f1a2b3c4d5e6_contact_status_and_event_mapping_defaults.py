"""contact status and event mapping defaults

Revision ID: f1a2b3c4d5e6
Revises: a8b9c0d1e2f3
Create Date: 2026-09-01 00:00:00.000000

Replaces Contact.is_active (boolean) with Contact.status (active | inactive |
pending), backfilling is_active=true -> status='active' and is_active=false ->
status='inactive' so no contact's campaign-send eligibility changes as a side
effect of this migration. Also adds EventMapping.default_status and
default_tags so an event_type's contact auto-creation can declare a lifecycle
status and tags to stamp onto contacts it creates. See
docs/prds/0005-contact-status-and-event-mapping-defaults.md.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "a8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "contacts",
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
    )
    op.execute(
        "UPDATE contacts SET status = CASE WHEN is_active THEN 'active' ELSE 'inactive' END"
    )
    op.alter_column("contacts", "status", server_default=None)
    op.drop_column("contacts", "is_active")

    op.add_column(
        "event_mappings", sa.Column("default_status", sa.String(), nullable=True)
    )
    op.add_column(
        "event_mappings",
        sa.Column("default_tags", postgresql.ARRAY(sa.String()), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("event_mappings", "default_tags")
    op.drop_column("event_mappings", "default_status")

    op.add_column(
        "contacts",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.execute("UPDATE contacts SET is_active = (status = 'active')")
    op.alter_column("contacts", "is_active", server_default=None)
    op.drop_column("contacts", "status")

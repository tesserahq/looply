"""add custom events

Revision ID: a2b3c4d5e6f7
Revises: f7a8b9c0d1e2
Create Date: 2026-09-04 00:00:00.000000

Custom Events slice of docs/prds/0002-contact-custom-fields-and-events.md - an
append-only log of named occurrences ingested from Linden domain events over NATS,
each tied to the contact it was resolved against. Also relaxes
contacts.created_by_id to nullable, since a contact auto-created from an ingested
event (unknown user.id) has no authenticated Looply user to attribute it to.

Named custom_events, not contact_custom_events: the contact link is one property
of an ingested event, not its primary identity - Looply's NATS subscription sees
every event type on the shared stream, not just contact-relevant ones (see
TrackedEventType, added in a later migration).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "contacts", "created_by_id", existing_type=postgresql.UUID(), nullable=True
    )

    op.create_table(
        "custom_events",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("properties", postgresql.JSONB(), nullable=False),
        sa.Column("raw_envelope", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="CASCADE"),
    )
    # Supports both the operator's per-contact event history read (user story 11)
    # and the segment resolver's custom_event has/has_not join (0001 Phase 2+).
    op.create_index(
        "ix_custom_events_contact_id_name",
        "custom_events",
        ["contact_id", "name"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_custom_events_contact_id_name",
        table_name="custom_events",
    )
    op.drop_table("custom_events")
    op.alter_column(
        "contacts", "created_by_id", existing_type=postgresql.UUID(), nullable=False
    )

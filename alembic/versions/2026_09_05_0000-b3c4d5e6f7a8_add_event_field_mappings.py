"""add event field mappings

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-09-05 00:00:00.000000

Host-configured derivation between Custom Events and Custom Fields: declares that
an ingested event of a given event_type should have a value extracted from its
event_data (by dot-path) and written onto a contact's custom field. This is
additive on top of docs/prds/0002-contact-custom-fields-and-events.md, whose
"Out of Scope" section explicitly left event-to-field derivation for later - the
two primitives are otherwise independent.

Also relaxes contact_custom_field_values.set_by_user_id to nullable, since a value
written by an EventFieldMapping during NATS ingestion has no authenticated caller.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "contact_custom_field_values",
        "set_by_user_id",
        existing_type=postgresql.UUID(),
        nullable=True,
    )

    op.create_table(
        "event_field_mappings",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("source_path", sa.String(), nullable=False),
        sa.Column("field_definition_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["field_definition_id"],
            ["custom_field_definitions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    # Looked up by event_type on every ingested event (see
    # app.tasks.process_nats_event_task) - active-row scoping comes from the global
    # soft-delete query filter, not this index.
    op.create_index(
        "ix_event_field_mappings_event_type",
        "event_field_mappings",
        ["event_type"],
    )
    # Prevents literal duplicate mappings while allowing one event_type to fan out
    # to multiple fields (or multiple paths of the same event to the same field).
    op.execute(
        "CREATE UNIQUE INDEX uq_event_field_mappings_event_source_field "
        "ON event_field_mappings (event_type, source_path, field_definition_id) "
        "WHERE deleted_at IS NULL"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX uq_event_field_mappings_event_source_field")
    op.drop_index(
        "ix_event_field_mappings_event_type", table_name="event_field_mappings"
    )
    op.drop_table("event_field_mappings")
    op.alter_column(
        "contact_custom_field_values",
        "set_by_user_id",
        existing_type=postgresql.UUID(),
        nullable=False,
    )

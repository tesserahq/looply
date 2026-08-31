"""add tracked event types

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-09-06 00:00:00.000000

The allow-list of event_types Looply actually acts on: Looply's NATS subscription
sees every event type on the shared stream (wildcard subject "com.>"), most of
which have nothing to do with contacts. An event whose type isn't registered here
is dropped before any DB work in app.tasks.process_nats_event_task - no Contact
resolution/auto-create, no custom_events row, no event_field_mappings applied.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tracked_event_types",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("created_by_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    # Looked up by exact event_type on every ingested NATS message (see
    # app.tasks.process_nats_event_task) - active-row scoping comes from the
    # global soft-delete query filter, not this index. Exact match (not
    # lower()'d) since event_type is a machine identifier emitted verbatim by
    # code, not human-typed like CustomFieldDefinition.name.
    op.execute(
        "CREATE UNIQUE INDEX uq_tracked_event_types_event_type "
        "ON tracked_event_types (event_type) "
        "WHERE deleted_at IS NULL"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX uq_tracked_event_types_event_type")
    op.drop_table("tracked_event_types")

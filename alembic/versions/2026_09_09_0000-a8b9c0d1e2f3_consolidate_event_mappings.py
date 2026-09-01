"""consolidate event mappings

Revision ID: a8b9c0d1e2f3
Revises: e6f7a8b9c0d1
Create Date: 2026-09-09 00:00:00.000000

Replaces tracked_event_types and the flat event_field_mappings table with a
two-level structure: event_mappings (one row per event_type, holding source and
the identity_target_field/identity_source_path that used to live on a flagged
is_identity_key=True event_field_mappings row) and event_field_mappings
restructured to hold only non-identity attributes, scoped to their parent by
event_mapping_id instead of a repeated event_type string. See
docs/prds/0004-event-mapping-consolidation.md.

Clean-slate: no production data exists in either table yet, so this drops and
recreates rather than backfilling.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table("event_field_mappings")
    op.drop_index("uq_tracked_event_types_event_type", table_name="tracked_event_types")
    op.drop_table("tracked_event_types")

    op.create_table(
        "event_mappings",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("identity_target_field", sa.String(), nullable=True),
        sa.Column("identity_source_path", sa.String(), nullable=True),
        sa.Column("created_by_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    # Looked up by exact event_type on every ingested NATS message (see
    # app.tasks.process_nats_event_task) - active-row scoping comes from the
    # global soft-delete query filter, not this index.
    op.execute(
        "CREATE UNIQUE INDEX uq_event_mappings_event_type "
        "ON event_mappings (event_type) "
        "WHERE deleted_at IS NULL"
    )

    op.create_table(
        "event_field_mappings",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("event_mapping_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("source_path", sa.String(), nullable=False),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("target_field", sa.String(), nullable=True),
        sa.Column("field_definition_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["event_mapping_id"], ["event_mappings.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["field_definition_id"],
            ["custom_field_definitions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    # Looked up by parent event_mapping_id on every ingested event.
    op.create_index(
        "ix_event_field_mappings_event_mapping_id",
        "event_field_mappings",
        ["event_mapping_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_event_field_mappings_event_mapping_id", table_name="event_field_mappings"
    )
    op.drop_table("event_field_mappings")

    op.execute("DROP INDEX uq_event_mappings_event_type")
    op.drop_table("event_mappings")

    op.create_table(
        "tracked_event_types",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("created_by_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_tracked_event_types_event_type "
        "ON tracked_event_types (event_type) "
        "WHERE deleted_at IS NULL"
    )

    op.create_table(
        "event_field_mappings",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("source_path", sa.String(), nullable=False),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("target_field", sa.String(), nullable=True),
        sa.Column("field_definition_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("is_identity_key", sa.Boolean(), nullable=False),
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
    op.create_index(
        "ix_event_field_mappings_event_type",
        "event_field_mappings",
        ["event_type"],
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_event_field_mappings_identity_key_per_event_type "
        "ON event_field_mappings (event_type) "
        "WHERE deleted_at IS NULL AND is_identity_key"
    )

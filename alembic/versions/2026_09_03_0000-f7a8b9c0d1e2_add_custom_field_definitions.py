"""add custom field definitions and contact.external_id

Revision ID: f7a8b9c0d1e2
Revises: e5f6a7b8c9d0
Create Date: 2026-09-03 00:00:00.000000

Custom Fields slice of docs/prds/0002-contact-custom-fields-and-events.md - explicitly
typed, named key/value attributes a host platform or operator can write onto any
contact, plus the Contact.external_id column that resolves contact identity for the
write endpoint. Custom Events (NATS ingestion) ships separately.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("contacts", sa.Column("external_id", sa.String(), nullable=True))
    # Partial unique index, not a column-level constraint: mirrors users.external_id
    # (see alembic/versions/init.py) so multiple contacts with external_id=NULL are
    # allowed (contacts created through Looply's own UI/import flow).
    op.create_index(
        "uq_contacts_external_id",
        "contacts",
        ["external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )

    op.create_table(
        "custom_field_definitions",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("value_type", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("created_by_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    # Partial, case-insensitive unique index scoped to active rows only, so a
    # soft-deleted definition's name can be reused (the PRD's "delete and recreate"
    # fix for a typo'd name or wrong value_type) - a plain unique constraint would
    # block exactly that, the same latent gap Segment.name has today.
    op.execute(
        "CREATE UNIQUE INDEX uq_custom_field_definitions_name "
        "ON custom_field_definitions (lower(name)) "
        "WHERE deleted_at IS NULL"
    )

    op.create_table(
        "contact_custom_field_values",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("field_definition_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("set_by_user_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["field_definition_id"],
            ["custom_field_definitions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["set_by_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "contact_id",
            "field_definition_id",
            name="uq_contact_custom_field_values_contact_field",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("contact_custom_field_values")
    op.execute("DROP INDEX uq_custom_field_definitions_name")
    op.drop_table("custom_field_definitions")
    op.drop_index("uq_contacts_external_id", table_name="contacts")
    op.drop_column("contacts", "external_id")

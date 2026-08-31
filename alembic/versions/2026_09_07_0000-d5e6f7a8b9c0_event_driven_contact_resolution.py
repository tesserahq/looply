"""event driven contact resolution

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-09-07 00:00:00.000000

Extends event_field_mappings so a single mapping can target either a built-in
Contact column (target_type="contact_field") or a custom field
(target_type="custom_field", the only kind that existed before this migration -
every existing row is backfilled to it). Exactly one mapping per event_type may
be flagged is_identity_key=True, naming the payload path and Contact column
(external_id or email) used to resolve/auto-create the contact for that
event_type - see docs/prds/0003-event-driven-contact-resolution.md.

Also adds Contact.source and TrackedEventType.source (provenance), and a partial
unique index on contacts.email so email is safe to use as an identity-key lookup
target. The email index is preceded by a duplicate-check that aborts the
migration if any pre-existing duplicate, non-null emails are found - no
automatic mutation of existing contact data.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- event_field_mappings: contact_field vs custom_field targets ---
    op.add_column(
        "event_field_mappings",
        sa.Column(
            "target_type",
            sa.String(),
            nullable=False,
            server_default="custom_field",
        ),
    )
    op.alter_column("event_field_mappings", "target_type", server_default=None)
    op.add_column(
        "event_field_mappings", sa.Column("target_field", sa.String(), nullable=True)
    )
    op.add_column(
        "event_field_mappings",
        sa.Column(
            "is_identity_key", sa.Boolean(), nullable=False, server_default="false"
        ),
    )
    op.alter_column("event_field_mappings", "is_identity_key", server_default=None)
    op.alter_column(
        "event_field_mappings",
        "field_definition_id",
        existing_type=sa.UUID(as_uuid=True),
        nullable=True,
    )
    # At most one active is_identity_key=True mapping per event_type.
    op.execute(
        "CREATE UNIQUE INDEX uq_event_field_mappings_identity_key_per_event_type "
        "ON event_field_mappings (event_type) "
        "WHERE deleted_at IS NULL AND is_identity_key"
    )

    # --- contacts: provenance + email uniqueness ---
    op.add_column("contacts", sa.Column("source", sa.String(), nullable=True))

    duplicate_emails = op.get_bind().execute(
        sa.text(
            "SELECT email FROM contacts WHERE email IS NOT NULL AND deleted_at IS NULL "
            "GROUP BY email HAVING COUNT(*) > 1"
        )
    ).fetchall()
    if duplicate_emails:
        emails = ", ".join(row[0] for row in duplicate_emails)
        raise RuntimeError(
            "Cannot add unique index on contacts.email - duplicate emails exist: "
            f"{emails}. Resolve these contacts manually, then re-run this migration."
        )
    op.create_index(
        "uq_contacts_email",
        "contacts",
        ["email"],
        unique=True,
        postgresql_where=sa.text("email IS NOT NULL AND deleted_at IS NULL"),
    )

    # --- tracked_event_types: provenance source stamped onto auto-created contacts ---
    op.add_column(
        "tracked_event_types", sa.Column("source", sa.String(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("tracked_event_types", "source")

    op.drop_index("uq_contacts_email", table_name="contacts")
    op.drop_column("contacts", "source")

    op.execute("DROP INDEX uq_event_field_mappings_identity_key_per_event_type")
    op.alter_column(
        "event_field_mappings",
        "field_definition_id",
        existing_type=sa.UUID(as_uuid=True),
        nullable=False,
    )
    op.drop_column("event_field_mappings", "is_identity_key")
    op.drop_column("event_field_mappings", "target_field")
    op.drop_column("event_field_mappings", "target_type")

"""Initialize the database

Revision ID: initialize_database
Revises:
Create Date: 2024-03-21

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "initialize_database"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


FTS_EXPR = " || ".join(
    [
        "setweight(to_tsvector('simple_unaccent', coalesce(first_name,'')), 'A')",
        "setweight(to_tsvector('simple_unaccent', coalesce(middle_name,'')), 'B')",
        "setweight(to_tsvector('simple_unaccent', coalesce(last_name,'')), 'A')",
        "setweight(to_tsvector('simple_unaccent', coalesce(company,'')), 'A')",
        "setweight(to_tsvector('simple_unaccent', coalesce(job,'')), 'B')",
        "setweight(to_tsvector('simple_unaccent', coalesce(email,'')), 'B')",
        "setweight(to_tsvector('simple_unaccent', coalesce(phone,'')), 'C')",
        "setweight(to_tsvector('simple_unaccent', coalesce(notes,'')), 'C')",
        "setweight(to_tsvector('simple_unaccent', coalesce(address_line_1,'')), 'D')",
        "setweight(to_tsvector('simple_unaccent', coalesce(address_line_2,'')), 'D')",
        "setweight(to_tsvector('simple_unaccent', coalesce(city,'')), 'D')",
        "setweight(to_tsvector('simple_unaccent', coalesce(state,'')), 'D')",
        "setweight(to_tsvector('simple_unaccent', coalesce(zip_code,'')), 'D')",
        "setweight(to_tsvector('simple_unaccent', coalesce(country,'')), 'D')",
    ]
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # Create text search configuration for unaccented text search
    # Ensure simple_unaccent config exists
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_ts_config WHERE cfgname = 'simple_unaccent'
            ) THEN
                CREATE TEXT SEARCH CONFIGURATION simple_unaccent ( COPY = simple );
                ALTER TEXT SEARCH CONFIGURATION simple_unaccent ALTER MAPPING
                    FOR hword, hword_part, word WITH unaccent, simple;
            END IF;
        END$$;
        """
    )

    op.create_table(
        "app_settings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("key", sa.String(length=50), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String, unique=True, nullable=True),
        sa.Column("username", sa.String, unique=True, nullable=True),
        sa.Column("external_id", sa.String, nullable=True),
        sa.Column("avatar_url", sa.String, nullable=True),
        sa.Column("first_name", sa.String, nullable=False),
        sa.Column("last_name", sa.String, nullable=False),
        sa.Column("provider", sa.String, nullable=True),
        sa.Column("confirmed_at", sa.DateTime, nullable=True),
        sa.Column("verified", sa.Boolean, default=False),
        sa.Column("verified_at", sa.DateTime, nullable=True),
        sa.Column(
            "created_at", sa.DateTime, nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime, nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )

    # Add a partial unique index for external_id
    op.create_index(
        "uq_users_external_id",
        "users",
        ["external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )

    # Create contacts table first
    op.create_table(
        "contacts",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("first_name", sa.String(), nullable=True),
        sa.Column("middle_name", sa.String(), nullable=True),
        sa.Column("last_name", sa.String(), nullable=True),
        sa.Column("company", sa.String(), nullable=True),
        sa.Column("job", sa.String(), nullable=True),
        sa.Column("contact_type", sa.String(), nullable=False),
        sa.Column("phone_type", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("website", sa.String(), nullable=True),
        sa.Column("address_line_1", sa.String(), nullable=True),
        sa.Column("address_line_2", sa.String(), nullable=True),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("state", sa.String(), nullable=True),
        sa.Column("zip_code", sa.String(), nullable=True),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        # Store preferences and consent per contact
        #     Global opt-in/out
        #     Category-level preferences (marketing, operational notices, billing, legal, etc.)
        #     Track consent timestamp and source
        sa.Column("created_by_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column(
            "fts",
            postgresql.TSVECTOR(),
            sa.Computed(FTS_EXPR, persisted=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "contact_lists",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("created_by_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "contact_list_members",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_list_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["contact_list_id"], ["contact_lists.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "contact_list_id",
            "contact_id",
            name="uq_contact_list_members_contact_list_id_contact_id",
        ),
    )

    op.create_table(
        "waiting_lists",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("created_by_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "waiting_list_members",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("waiting_list_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("contact_id", sa.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["waiting_list_id"], ["waiting_lists.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "waiting_list_id",
            "contact_id",
            name="uq_waiting_list_members_waiting_list_id_contact_id",
        ),
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("contact_list_members")
    op.drop_table("contact_lists")
    op.drop_table("contacts")

    # Drop the partial unique index
    op.drop_index("uq_users_external_id", table_name="users")
    op.drop_table("users")
    op.drop_table("app_settings")

    # Drop text search configuration
    op.execute("DROP TEXT SEARCH CONFIGURATION IF EXISTS simple_unaccent;")

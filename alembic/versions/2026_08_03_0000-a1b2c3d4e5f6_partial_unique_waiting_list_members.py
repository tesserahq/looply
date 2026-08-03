"""Scope waiting list member uniqueness to active rows only

Revision ID: a1b2c3d4e5f6
Revises: ddaafcc6394c
Create Date: 2026-08-03 00:00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "ddaafcc6394c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_waiting_list_members_waiting_list_id_contact_id",
        "waiting_list_members",
        type_="unique",
    )
    op.create_index(
        "uq_waiting_list_members_waiting_list_id_contact_id",
        "waiting_list_members",
        ["waiting_list_id", "contact_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_waiting_list_members_waiting_list_id_contact_id",
        table_name="waiting_list_members",
    )
    op.create_unique_constraint(
        "uq_waiting_list_members_waiting_list_id_contact_id",
        "waiting_list_members",
        ["waiting_list_id", "contact_id"],
    )

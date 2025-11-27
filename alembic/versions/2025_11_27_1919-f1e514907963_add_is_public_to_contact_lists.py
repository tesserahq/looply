"""Add is_public to contact lists

Revision ID: f1e514907963
Revises: 0ca65f259cd5
Create Date: 2025-11-27 19:19:54.756824

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1e514907963"
down_revision: Union[str, None] = "0ca65f259cd5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "contact_lists",
        sa.Column("is_public", sa.Boolean(), nullable=False, default=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("contact_lists", "is_public")

"""Add custo action

Revision ID: 8a7c515dafc3
Revises: f1e514907963
Create Date: 2025-12-10 12:08:49.033837

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8a7c515dafc3"
down_revision: Union[str, None] = "f1e514907963"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "contact_interactions",
        sa.Column("custom_action_description", sa.String(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("contact_interactions", "custom_action_description")

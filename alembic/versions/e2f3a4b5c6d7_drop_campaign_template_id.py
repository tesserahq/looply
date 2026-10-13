"""drop campaign template_id

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-10-13 00:00:00.000000

Campaigns own their content (docs/prds/0007-campaign-owned-email-content.md).
The one-off backfill copied every legacy template's content onto its
campaign and the Sendly templates were deleted (#178, #179), so the legacy
reference is dropped. Downgrade restores the column empty.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("campaigns", "template_id")


def downgrade() -> None:
    op.add_column(
        "campaigns", sa.Column("template_id", sa.UUID(as_uuid=True), nullable=True)
    )

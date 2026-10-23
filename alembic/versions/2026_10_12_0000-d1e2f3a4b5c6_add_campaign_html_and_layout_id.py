"""add campaign html and layout_id

Revision ID: d1e2f3a4b5c6
Revises: c9d0e1f2a3b4
Create Date: 2026-10-12 00:00:00.000000

Campaigns now own their email body instead of pointing at a per-campaign
Sendly template (docs/prds/0007-campaign-owned-email-content.md). `html` is
the body, sent to Sendly inline; `layout_id` is the Sendly layout to wrap it
in. Both nullable for drafts. Existing rows are left empty here — the
one-off backfill copies each campaign's template content in, and
`template_id` is dropped in a later migration once that's done.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("campaigns", sa.Column("html", sa.Text(), nullable=True))
    op.add_column(
        "campaigns", sa.Column("layout_id", sa.UUID(as_uuid=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("campaigns", "layout_id")
    op.drop_column("campaigns", "html")

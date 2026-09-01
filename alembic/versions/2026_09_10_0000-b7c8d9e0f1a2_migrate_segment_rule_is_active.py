"""migrate segment rule is_active to status

Revision ID: b7c8d9e0f1a2
Revises: f1a2b3c4d5e6
Create Date: 2026-09-10 00:00:00.000000

f1a2b3c4d5e6 dropped Contact.is_active in favor of Contact.status and removed
ContactFieldName.IS_ACTIVE from the segment rule schema, but never touched
existing Segment.rule JSON already stored in the database. Any segment whose
rule tree contains a `contact_field` leaf with `field: "is_active"` now fails
Pydantic validation on read (GET /segments 500s for everyone, since
fastapi_pagination validates the whole page at once) because "is_active" is
no longer a valid ContactFieldName and its boolean value no longer matches
the field's `Union[str, list[str]]` value type.

This migration walks every stored rule tree and rewrites each such leaf in
place: field is_active -> status, value True -> "active" / False ->
"inactive", preserving the existing EQ/NEQ operator (the only operators
is_active ever allowed).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import table, column
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

segments_table = table(
    "segments",
    column("id", UUID(as_uuid=True)),
    column("rule", JSONB),
)


def _migrate_node(node, changed):
    """Recursively rewrite is_active leaves to status leaves.

    `changed` is a single-element list used as an out-param: comparing the
    rewritten tree against the original by `!=` doesn't work here since the
    rewrite mutates dicts in place, so both sides of the comparison would end
    up pointing at (or containing) the same mutated objects.
    """
    if not isinstance(node, dict):
        return node
    if node.get("type") == "contact_field" and node.get("field") == "is_active":
        node["field"] = "status"
        node["value"] = "active" if node.get("value") else "inactive"
        changed.append(True)
        return node
    if "conditions" in node:
        node["conditions"] = [_migrate_node(child, changed) for child in node["conditions"]]
    return node


def _unmigrate_node(node, changed):
    """Best-effort reverse: status leaves that came from is_active back to
    is_active leaves. Lossy for status='pending', which has no boolean
    equivalent - mapped to False, matching the lossy is_active backfill in
    f1a2b3c4d5e6 (status='pending' has no prior representation either)."""
    if not isinstance(node, dict):
        return node
    if node.get("type") == "contact_field" and node.get("field") == "status":
        node["field"] = "is_active"
        node["value"] = node.get("value") == "active"
        changed.append(True)
        return node
    if "conditions" in node:
        node["conditions"] = [_unmigrate_node(child, changed) for child in node["conditions"]]
    return node


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()
    rows = connection.execute(sa.select(segments_table.c.id, segments_table.c.rule)).fetchall()
    for row_id, rule in rows:
        if not isinstance(rule, dict) or "root" not in rule:
            continue
        changed: list = []
        new_root = _migrate_node(rule["root"], changed)
        if changed:
            connection.execute(
                segments_table.update()
                .where(segments_table.c.id == row_id)
                .values(rule={"root": new_root})
            )


def downgrade() -> None:
    """Downgrade schema."""
    connection = op.get_bind()
    rows = connection.execute(sa.select(segments_table.c.id, segments_table.c.rule)).fetchall()
    for row_id, rule in rows:
        if not isinstance(rule, dict) or "root" not in rule:
            continue
        changed: list = []
        new_root = _unmigrate_node(rule["root"], changed)
        if changed:
            connection.execute(
                segments_table.update()
                .where(segments_table.c.id == row_id)
                .values(rule={"root": new_root})
            )

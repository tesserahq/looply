from sqlalchemy.orm import Mapped, mapped_column
from app.models.mixins import TimestampMixin, SoftDeleteMixin
from sqlalchemy import Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
import uuid

from app.db import Base


class Segment(Base, TimestampMixin, SoftDeleteMixin):
    """Segment model for the application.

    A saved, reusable, rule-based filter over Looply's entire contact base -
    not scoped to any one contact list. "is a member of list X" is just one
    filterable condition (see app.schemas.segment_rule) among others, rather
    than a required, separate concept a segment narrows down. See
    docs/prds/0001-campaign-segments.md for the full design.
    """

    __tablename__ = "segments"
    __table_args__ = (UniqueConstraint("name", name="uq_segments_name"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    # The validated SegmentRuleCreate tree's model_dump(mode="json") - see
    # app.schemas.segment_rule. Deliberately no contact_list_id column: a
    # segment has no owning list, only an optional list_membership leaf.
    rule: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_by_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

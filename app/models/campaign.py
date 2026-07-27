from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.mixins import TimestampMixin, SoftDeleteMixin
from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
import uuid

from app.constants.campaign import CampaignStatus
from app.db import Base


class Campaign(Base, TimestampMixin, SoftDeleteMixin):
    """Campaign model for the application.
    Represents a one-time send of a Looply contact list through Sendly.
    See docs/campaign.md for the full domain spec.
    """

    __tablename__ = "campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default=CampaignStatus.DRAFT.value, index=True
    )
    contact_list_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contact_lists.id"), nullable=False
    )
    # project_id and template_id reference Sendly's own domain, not local tables,
    # so they are plain columns rather than foreign keys. Both are nullable so a
    # campaign can be drafted before its Sendly project/template is finalized.
    project_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    template_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    template_variables: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    from_email: Mapped[str | None] = mapped_column(String, nullable=True)
    subject: Mapped[str | None] = mapped_column(String, nullable=True)
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    batch_id: Mapped[str | None] = mapped_column(String, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

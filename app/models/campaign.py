from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.mixins import TimestampMixin, SoftDeleteMixin
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
import uuid

from app.constants.campaign import CampaignStatus
from app.db import Base


class Campaign(Base, TimestampMixin, SoftDeleteMixin):
    """Campaign model for the application.
    Represents a one-time send of a Looply segment's audience through Sendly.
    See docs/campaign.md for the full domain spec.
    """

    __tablename__ = "campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default=CampaignStatus.DRAFT.value, index=True
    )
    # A campaign's audience is always "resolve this segment" - there's no
    # separate list step. The common "send to this whole list" case is just
    # a segment with a single list_membership condition (see
    # docs/prds/0001-campaign-segments.md).
    segment_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("segments.id"), nullable=False
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

    # Result counts, refreshed from Sendly's get_broadcast() by
    # poll_campaign_engagement while the campaign is within its polling
    # window. Not delivery-event data of Looply's own - see docs/campaign.md.
    delivered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bounced_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    complained_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    opened_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clicked_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # engagement_last_synced_at only advances after a fully successful
    # poll_campaign_engagement pass for this campaign, so it can be trusted
    # as a "data as of" indicator even though per-item polling failures are
    # swallowed. engagement_polling_expires_at is fixed at completed_at plus
    # the global polling window (see Settings.engagement_polling_window_days)
    # and never extended.
    engagement_last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    engagement_polling_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

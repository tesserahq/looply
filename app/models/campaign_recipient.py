from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.mixins import TimestampMixin
from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db import Base


class CampaignRecipient(Base, TimestampMixin):
    """Snapshot of a campaign's audience at the moment it was sent.

    Recorded once, right after Sendly accepts the broadcast (see
    SendCampaignCommand). contact_id is a live reference, not a copy of the
    contact's data at send time - see docs/campaign.md.
    """

    __tablename__ = "campaign_recipients"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id", "contact_id", name="uq_campaign_recipients_campaign_contact"
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False
    )
    contact_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False
    )
    # First-occurrence timestamps only, filled in by poll_campaign_engagement
    # from Sendly's per-recipient results, matched by contact_id (sent as
    # client_reference_id) rather than the mutable email address. Not a
    # per-event log - see docs/campaign.md.
    opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # viewonly: reads join to the live Contact for display (e.g. the
    # recipients list endpoint); writes still go through contact_id alone,
    # so this doesn't turn the "live reference, not a copy" contract above
    # into a snapshot.
    contact = relationship("Contact", viewonly=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

import uuid

from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import TimestampMixin


class CampaignTag(Base, TimestampMixin):
    """A campaign's assignment to a Tag. Membership only, current state - no
    SoftDeleteMixin, mirroring ContactTag.
    """

    __tablename__ = "campaign_tags"
    __table_args__ = (
        UniqueConstraint("campaign_id", "tag_id", name="uq_campaign_tags_campaign_tag"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    tag_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), nullable=False
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

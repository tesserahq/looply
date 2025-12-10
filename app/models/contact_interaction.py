from sqlalchemy.orm import Mapped, mapped_column
from app.models.mixins import TimestampMixin, SoftDeleteMixin
from sqlalchemy import Column, ForeignKey, String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, timezone

from app.db import Base


class ContactInteraction(Base, TimestampMixin, SoftDeleteMixin):
    """ContactInteraction model for tracking interactions with contacts.

    This model represents an interaction note with a contact, including:
    - The nature of the interaction (note text)
    - When the interaction occurred
    - Optional action items with timestamps for follow-up
    """

    __tablename__ = "contact_interactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contact_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False, index=True
    )
    note: Mapped[str] = mapped_column(Text, nullable=False)
    """The interaction note text (typically 500-1000 characters)."""

    interaction_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    """Timestamp when the interaction actually occurred."""

    action: Mapped[str | None] = mapped_column(String, nullable=True)
    """Optional action item for follow-up (e.g., 'Follow up in 2 weeks', 'Send proposal')."""

    custom_action_description: Mapped[str | None] = mapped_column(String, nullable=True)
    """Optional custom action description for follow-up (e.g., 'Send proposal')."""

    action_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    """Optional timestamp for when the action should be taken."""

    created_by_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    """ID of the user who created this interaction note."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

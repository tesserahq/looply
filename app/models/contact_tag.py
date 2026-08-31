import uuid

from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import TimestampMixin


class ContactTag(Base, TimestampMixin):
    """A contact's assignment to a Tag. Membership only, current state - no
    SoftDeleteMixin, same reasoning as ContactCustomFieldValue: removing an
    assignment is a hard delete, distinct from soft-deleting the Tag itself.
    """

    __tablename__ = "contact_tags"
    __table_args__ = (
        UniqueConstraint("contact_id", "tag_id", name="uq_contact_tags_contact_tag"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contact_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    tag_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), nullable=False
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

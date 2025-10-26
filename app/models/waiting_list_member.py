from sqlalchemy.orm import Mapped, mapped_column
from app.models.mixins import TimestampMixin, SoftDeleteMixin
from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db import Base
from app.constants.waiting_list import WaitingListMemberStatus


class WaitingListMember(Base, TimestampMixin, SoftDeleteMixin):
    """WaitingListMember model for the application.
    This model represents the relationship between waiting lists and contacts.
    """

    __tablename__ = "waiting_list_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    waiting_list_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("waiting_lists.id"), nullable=False
    )
    contact_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String, nullable=False, default=WaitingListMemberStatus.PENDING
    )

    # Relationships could be added here if needed
    # waiting_list = relationship("WaitingList", back_populates="members")
    # contact = relationship("Contact", back_populates="waiting_lists")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

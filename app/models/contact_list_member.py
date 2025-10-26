from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.models.mixins import TimestampMixin, SoftDeleteMixin
from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db import Base


class ContactListMember(Base, TimestampMixin, SoftDeleteMixin):
    """ContactListMember model for the application.
    This model represents the relationship between contact lists and contacts.
    """

    __tablename__ = "contact_list_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contact_list_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contact_lists.id"), nullable=False
    )
    contact_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False
    )

    # Relationships could be added here if needed
    # contact_list = relationship("ContactList", back_populates="members")
    # contact = relationship("Contact", back_populates="contact_lists")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

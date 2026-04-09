from sqlalchemy.orm import Mapped, mapped_column, column_property
from app.models.mixins import TimestampMixin, SoftDeleteMixin
from sqlalchemy import Boolean, Column, ForeignKey, String, func, select
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db import Base


class ContactList(Base, TimestampMixin, SoftDeleteMixin):
    """ContactList model for the application.
    This model represents a list of contacts in the system.
    """

    __tablename__ = "contact_lists"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    # Note: You might want to add relationships to contacts if needed
    # members = relationship("ContactListMember", back_populates="contact_list")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


# Defined after class to avoid circular import with ContactListMember
from app.models.contact_list_member import ContactListMember  # noqa: E402

ContactList.contact_count = column_property(
    select(func.count(ContactListMember.id))
    .where(
        ContactListMember.contact_list_id == ContactList.id,
        ContactListMember.deleted_at.is_(None),
    )
    .correlate_except(ContactListMember)
    .scalar_subquery()
)

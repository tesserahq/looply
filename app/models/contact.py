from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.models.mixins import TimestampMixin, SoftDeleteMixin
from sqlalchemy import Column, ForeignKey, String, DateTime, Text, Boolean, Computed
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from sqlalchemy.types import TypeDecorator, CHAR
import uuid

from app.db import Base


class Contact(Base, TimestampMixin, SoftDeleteMixin):
    """Contact model for the application.
    This model represents a contact in the system.
    """

    __tablename__ = "contacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name: Mapped[str | None] = mapped_column(String, nullable=True)
    middle_name: Mapped[str | None] = mapped_column(String, nullable=True)
    last_name: Mapped[str | None] = mapped_column(String, nullable=True)
    company: Mapped[str | None] = mapped_column(String, nullable=True)
    job: Mapped[str | None] = mapped_column(String, nullable=True)
    contact_type: Mapped[str] = mapped_column(String, nullable=False)
    phone_type: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    website: Mapped[str | None] = mapped_column(String, nullable=True)
    address_line_1: Mapped[str | None] = mapped_column(String, nullable=True)
    address_line_2: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    state: Mapped[str | None] = mapped_column(String, nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String, nullable=True)
    country: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Generated full-text search column (maintained by PostgreSQL)
    fts: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            " || ".join(
                [
                    "setweight(to_tsvector('simple_unaccent', coalesce(first_name,'')), 'A')",
                    "setweight(to_tsvector('simple_unaccent', coalesce(middle_name,'')), 'B')",
                    "setweight(to_tsvector('simple_unaccent', coalesce(last_name,'')), 'A')",
                    "setweight(to_tsvector('simple_unaccent', coalesce(company,'')), 'A')",
                    "setweight(to_tsvector('simple_unaccent', coalesce(job,'')), 'B')",
                    "setweight(to_tsvector('simple_unaccent', coalesce(email,'')), 'B')",
                    "setweight(to_tsvector('simple_unaccent', coalesce(phone,'')), 'C')",
                    "setweight(to_tsvector('simple_unaccent', coalesce(notes,'')), 'C')",
                    "setweight(to_tsvector('simple_unaccent', coalesce(address_line_1,'')), 'D')",
                    "setweight(to_tsvector('simple_unaccent', coalesce(address_line_2,'')), 'D')",
                    "setweight(to_tsvector('simple_unaccent', coalesce(city,'')), 'D')",
                    "setweight(to_tsvector('simple_unaccent', coalesce(state,'')), 'D')",
                    "setweight(to_tsvector('simple_unaccent', coalesce(zip_code,'')), 'D')",
                    "setweight(to_tsvector('simple_unaccent', coalesce(country,'')), 'D')",
                ]
            ),
            persisted=True,
        ),
        nullable=False,
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def full_name(self) -> str:
        """Get the full name of the contact."""
        name_parts = []
        if self.first_name:
            name_parts.append(self.first_name)
        if self.middle_name:
            name_parts.append(self.middle_name)
        if self.last_name:
            name_parts.append(self.last_name)
        return " ".join(name_parts) if name_parts else ""

    @property
    def display_name(self) -> str:
        """Get a display name for the contact."""
        return self.full_name

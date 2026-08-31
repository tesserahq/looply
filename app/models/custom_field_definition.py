from sqlalchemy.orm import Mapped, mapped_column
from app.models.mixins import TimestampMixin, SoftDeleteMixin
from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db import Base


class CustomFieldDefinition(Base, TimestampMixin, SoftDeleteMixin):
    """A named, explicitly-typed custom field a host platform or operator can write
    values for on any contact. See docs/prds/0002-contact-custom-fields-and-events.md.

    name and value_type are immutable once set - a definition must be soft-deleted and
    recreated to change either. Uniqueness of name (case-insensitive, active rows only)
    is enforced by a partial index in the migration, not a column-level constraint here,
    so a soft-deleted definition's name can be reused.
    """

    __tablename__ = "custom_field_definitions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    # FieldValueType's value - stored as plain text (see app.schemas.custom_field_definition),
    # matching how Contact.contact_type stores ContactType, rather than a native Postgres enum.
    value_type: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

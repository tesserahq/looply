import uuid

from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import SoftDeleteMixin, TimestampMixin


class Tag(Base, TimestampMixin, SoftDeleteMixin):
    """A named label shared by contacts and campaigns for free-form
    categorization. Unlike CustomFieldDefinition, a tag's name is editable in
    place (see TagRepository.update_tag) since no typed data depends on it.

    Uniqueness of name (case-insensitive, active rows only) is enforced by a
    partial index in the migration, not a column-level constraint here, so a
    soft-deleted tag's name can be reused by a newly created row - see
    TagRepository.get_or_create_tags.
    """

    __tablename__ = "tags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_by_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

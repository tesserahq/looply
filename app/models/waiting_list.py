from sqlalchemy.orm import Mapped, mapped_column
from app.models.mixins import TimestampMixin, SoftDeleteMixin
from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db import Base


class WaitingList(Base, TimestampMixin, SoftDeleteMixin):
    """WaitingList model for the application.
    This model represents a waiting list in the system.
    """

    __tablename__ = "waiting_lists"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

from sqlalchemy import Column, ForeignKey, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
import uuid

from app.db import Base
from app.models.mixins import TimestampMixin


class Import(Base, TimestampMixin):
    """Import model for tracking batch contact imports.

    This model stores information about batch contact imports including
    the settings used, processing statistics, and the user who performed the import.
    """

    __tablename__ = "imports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # JSON field to store import settings (e.g., file_name and other metadata)
    settings: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Statistics about the import process
    processed_contacts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_contacts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Foreign key to the user who performed the import
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

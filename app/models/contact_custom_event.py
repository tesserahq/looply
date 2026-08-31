from sqlalchemy.orm import Mapped, mapped_column
from app.models.mixins import TimestampMixin
from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
import uuid

from app.db import Base


class ContactCustomEvent(Base, TimestampMixin):
    """An append-only occurrence recorded against a contact, ingested from a Linden
    domain event over NATS. No SoftDeleteMixin and no update/upsert method - every
    ingested event is its own row (see docs/prds/0002-contact-custom-fields-and-events.md,
    "Custom Events"). Unlike CustomFieldDefinition, event names need no upfront
    definition - the operator UI derives a browsable list from what's actually been
    recorded.
    """

    __tablename__ = "contact_custom_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contact_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    # The envelope's event_type (e.g. "com.mylinden.person.updated"). Free-form -
    # there's no FieldValueType-style lock to enforce, so nothing to pre-register.
    name: Mapped[str] = mapped_column(String, nullable=False)
    # The envelope's time.
    occurred_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False)
    # The envelope's event_data, stored as-is - Looply never interprets its shape.
    properties: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # The full incoming envelope, verbatim, for audit/debugging - only name/
    # occurred_at/properties are used for segment resolution (see the PRD).
    raw_envelope: Mapped[dict] = mapped_column(JSONB, nullable=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

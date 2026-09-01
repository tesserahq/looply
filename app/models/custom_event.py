from sqlalchemy.orm import Mapped, mapped_column
from app.models.mixins import TimestampMixin
from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
import uuid

from app.db import Base


class CustomEvent(Base, TimestampMixin):
    """An append-only occurrence ingested from a Linden domain event over NATS, tied
    to the contact it was resolved against.

    Deliberately not named ContactCustomEvent: Looply's NATS subscription sees every
    event type on the shared stream, not just contact-relevant ones - only event
    types with a registered EventMapping are ever turned into a row here (see
    app.tasks.process_nats_event_task). The contact link is one property of an
    event, not its primary identity.

    No SoftDeleteMixin and no update/upsert method - every ingested event is its
    own row (see docs/prds/0002-contact-custom-fields-and-events.md, "Custom
    Events").
    """

    __tablename__ = "custom_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contact_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    # The envelope's event_type (e.g. "com.mylinden.person.updated"). Matched
    # against EventMapping.event_type at ingestion time, but stored as a plain
    # string rather than a FK - a recorded event is a historical fact that should
    # survive the EventMapping registration later being deleted.
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

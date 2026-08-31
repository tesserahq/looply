from sqlalchemy.orm import Mapped, mapped_column
from app.models.mixins import TimestampMixin, SoftDeleteMixin
from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db import Base


class TrackedEventType(Base, TimestampMixin, SoftDeleteMixin):
    """The allow-list of event_types Looply actually acts on out of everything it
    receives on the shared NATS stream (subscribed via the wildcard subject
    "com.>" - see app.messaging.nats_subscriber and run_nats_worker.py).

    Looply sees every event type Linden (or any host) publishes, most of which have
    nothing to do with contacts. An event whose type isn't registered here is
    dropped before any DB work - no Contact resolution/auto-create, no CustomEvent
    row, no EventFieldMapping applied (see app.tasks.process_nats_event_task).
    Mirrors CustomFieldDefinition's role for fields: an explicit, operator/host-
    controlled registration rather than implicit inference from traffic.
    """

    __tablename__ = "tracked_event_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Exact match against the envelope's event_type. Unique (active rows only) -
    # see the migration for the partial index.
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    # Stamped onto Contact.source for every contact auto-created while ingesting
    # this event_type (see docs/prds/0003-event-driven-contact-resolution.md).
    # Nullable so existing registrations don't need a value before that PRD ships;
    # a null source here simply leaves Contact.source unset on auto-create.
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    # Null for host API calls, set to the operator's user id when created through
    # the UI - mirrors CustomFieldDefinition.created_by_id.
    created_by_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

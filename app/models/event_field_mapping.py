from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.mixins import TimestampMixin, SoftDeleteMixin
from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db import Base


class EventFieldMapping(Base, TimestampMixin, SoftDeleteMixin):
    """Declares that an ingested NATS event of a given event_type should have a
    value extracted from its event_data and written onto a contact's custom field.

    Host-configured derivation between Custom Events and Custom Fields - the PRD's
    two primitives are otherwise independent (see
    docs/prds/0002-contact-custom-fields-and-events.md, "Out of Scope" ->
    "Event-to-field derivation/aggregation"). Direct path extraction only - no
    counting/aggregation. Immutable once created (event_type, source_path, and
    field_definition_id together define the mapping) - delete and recreate to
    change any of them, same rationale as CustomFieldDefinition.name/value_type.
    """

    __tablename__ = "event_field_mappings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Exact match against the envelope's event_type (e.g. "com.mylinden.person.created").
    # No wildcards - keep matching simple; revisit if a real need for it shows up. Not
    # a FK to TrackedEventType - a mapping only has any effect once/if its event_type
    # is also tracked (see app.tasks.process_nats_event_task), but can be pre-created
    # before that registration exists.
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    # Dot-path into event_data (e.g. "account.family_member_count"). Resolved at
    # ingestion time - if any segment is missing, the mapping is silently skipped
    # for that event (see app.tasks.process_nats_event_task).
    source_path: Mapped[str] = mapped_column(String, nullable=False)
    field_definition_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("custom_field_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Null for host API calls, set to the operator's user id when created through
    # the UI - mirrors CustomFieldDefinition.created_by_id.
    created_by_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    field_definition = relationship("CustomFieldDefinition", lazy="joined")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def field_name(self) -> str:
        """The target field definition's name - denormalized for the read schema."""
        return self.field_definition.name

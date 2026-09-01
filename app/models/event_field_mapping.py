from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.mixins import TimestampMixin, SoftDeleteMixin
from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db import Base

# Real, settable Contact columns a "contact_field" mapping is allowed to target.
# Deliberately a fixed allow-list, not a free string, so a typo'd target_field
# fails loudly (422) instead of silently becoming a no-op mapping.
CONTACT_FIELD_TARGETS = frozenset(
    {
        "external_id",
        "first_name",
        "middle_name",
        "last_name",
        "company",
        "job",
        "phone",
        "email",
        "website",
        "address_line_1",
        "address_line_2",
        "city",
        "state",
        "zip_code",
        "country",
        "notes",
    }
)


class EventFieldMapping(Base, TimestampMixin, SoftDeleteMixin):
    """One non-identity attribute of its parent EventMapping: declares that a
    value extracted (by dot-path) from an ingested event's event_data should be
    written either onto a contact's custom field, or directly onto a built-in
    Contact column, once that event's identity mapping (on the parent
    EventMapping) has resolved which contact it belongs to.

    Host-configured derivation between Custom Events and Custom Fields/Contact
    attributes - the PRD's own primitives are otherwise independent (see
    docs/prds/0002-contact-custom-fields-and-events.md, "Out of Scope" ->
    "Event-to-field derivation/aggregation"). Direct path extraction only - no
    counting/aggregation.

    Editable in place (see app.models.event_mapping.EventMapping's docstring for
    the immutability-reversal rationale) - source_path, target_type,
    target_field, and field_definition_id can all be updated without deleting
    and recreating the row, unlike before docs/prds/0004-event-mapping-
    consolidation.md.
    """

    __tablename__ = "event_field_mappings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_mapping_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("event_mappings.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Dot-path into event_data (e.g. "person.account.family_member_count"). Resolved
    # at ingestion time - if any segment is missing, the mapping is silently skipped
    # for that event (see app.tasks.process_nats_event_task).
    source_path: Mapped[str] = mapped_column(String, nullable=False)
    # "contact_field" writes directly onto a built-in Contact column (target_field
    # names it, from CONTACT_FIELD_TARGETS); "custom_field" writes onto a
    # CustomFieldDefinition's value (field_definition_id names it), same as before
    # this column existed.
    target_type: Mapped[str] = mapped_column(String, nullable=False)
    # Set (and only meaningful) when target_type="contact_field" - the Contact
    # column name to write to. Validated against CONTACT_FIELD_TARGETS at write
    # time, not a free string.
    target_field: Mapped[str | None] = mapped_column(String, nullable=True)
    # Set (and required) when target_type="custom_field" - nullable so a
    # contact_field mapping doesn't need a definition at all.
    field_definition_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("custom_field_definitions.id", ondelete="CASCADE"),
        nullable=True,
    )
    # Null for host API calls, set to the operator's user id when created through
    # the UI - mirrors CustomFieldDefinition.created_by_id.
    created_by_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    event_mapping = relationship(
        "EventMapping", back_populates="field_mappings", lazy="joined"
    )
    field_definition = relationship("CustomFieldDefinition", lazy="joined")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def field_name(self) -> str | None:
        """The target field definition's name - denormalized for the read schema.
        None for a contact_field mapping (target_field is the read-schema
        equivalent there)."""
        return self.field_definition.name if self.field_definition else None

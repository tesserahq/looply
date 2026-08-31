from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.mixins import TimestampMixin, SoftDeleteMixin
from sqlalchemy import Boolean, Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db import Base

# Real, settable Contact columns a "contact_field" mapping is allowed to target.
# Deliberately a fixed allow-list, not a free string, so a typo'd target_field
# fails loudly (422) instead of silently becoming a no-op mapping. "external_id"
# and "email" are also the only two valid targets for is_identity_key=True (see
# below) since they're the only Contact columns with a uniqueness guarantee.
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

IDENTITY_KEY_TARGETS = frozenset({"external_id", "email"})


class EventFieldMapping(Base, TimestampMixin, SoftDeleteMixin):
    """Declares that an ingested NATS event of a given event_type should have a
    value extracted from its event_data (by dot-path) and written either onto a
    contact's custom field, or directly onto a built-in Contact column.

    Host-configured derivation between Custom Events and Custom Fields/Contact
    attributes - the PRD's own primitives are otherwise independent (see
    docs/prds/0002-contact-custom-fields-and-events.md, "Out of Scope" ->
    "Event-to-field derivation/aggregation"). Direct path extraction only - no
    counting/aggregation. Immutable once created (event_type, source_path, and
    target together define the mapping) - delete and recreate to change any of
    them, same rationale as CustomFieldDefinition.name/value_type.

    Exactly one mapping per event_type may have is_identity_key=True - it names
    the payload path and Contact column (external_id or email) used to resolve
    or auto-create the Contact for that event_type (see
    docs/prds/0003-event-driven-contact-resolution.md). All other mappings just
    fill in an attribute once the contact is already resolved.
    """

    __tablename__ = "event_field_mappings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Exact match against the envelope's event_type (e.g. "com.mylinden.person.created").
    # No wildcards - keep matching simple; revisit if a real need for it shows up. Not
    # a FK to TrackedEventType - a mapping only has any effect once/if its event_type
    # is also tracked (see app.tasks.process_nats_event_task), but can be pre-created
    # before that registration exists.
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    # Dot-path into event_data (e.g. "person.account.family_member_count"). Resolved
    # at ingestion time - if any segment is missing, the mapping is silently skipped
    # for that event (see app.tasks.process_nats_event_task), unless it's the
    # is_identity_key mapping, in which case the whole event is dropped instead.
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
    # True for exactly one mapping per event_type - see class docstring. Only
    # valid alongside target_type="contact_field" and
    # target_field in IDENTITY_KEY_TARGETS.
    is_identity_key: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
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
    def field_name(self) -> str | None:
        """The target field definition's name - denormalized for the read schema.
        None for a contact_field mapping (target_field is the read-schema
        equivalent there)."""
        return self.field_definition.name if self.field_definition else None

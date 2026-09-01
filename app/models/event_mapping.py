from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.mixins import TimestampMixin, SoftDeleteMixin
from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
import uuid

from app.db import Base

# Real, settable Contact columns an identity mapping is allowed to target - the
# only two Contact columns with a uniqueness guarantee, same allow-list
# EventFieldMapping.CONTACT_FIELD_TARGETS draws its identity subset from.
IDENTITY_KEY_TARGETS = frozenset({"external_id", "email"})


class EventMapping(Base, TimestampMixin, SoftDeleteMixin):
    """Declares that Looply should act on ingested NATS events of a given
    event_type: which payload path + Contact column identifies the contact for
    that event_type (identity_source_path/identity_target_field), and what
    provenance to stamp on a contact auto-created from it (source). Its
    EventFieldMapping children each declare one additional attribute (built-in
    Contact column or custom field) to fill in once the contact is resolved.

    Replaces the old, separate TrackedEventType allow-list: an event_type with
    no EventMapping row is untracked and dropped before any DB work (see
    app.tasks.process_nats_event_task) - registering an event_type and
    configuring its identity are now the same act, not two. See
    docs/prds/0004-event-mapping-consolidation.md.

    Unlike its EventFieldMapping children before this PRD, both this row's
    identity columns and each child's attributes are editable in place
    (repository update methods) rather than delete-and-recreate-only - a
    deliberate reversal of 0002/0003's immutability rule, accepting that a
    contact resolved under an old identity rule may silently disagree with one
    resolved after an edit, in exchange for a misconfigured mapping being a
    one-step fix. See the PRD's "Further Notes" for the accepted trade-off.
    """

    __tablename__ = "event_mappings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Exact match against the envelope's event_type (e.g. "com.mylinden.person.created").
    # No wildcards - keep matching simple; revisit if a real need for it shows up.
    # Unique among active rows (partial index in the migration, not a column-level
    # constraint, so a soft-deleted row's event_type can be reused).
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    # Stamped onto Contact.source for every contact auto-created while ingesting
    # this event_type (e.g. "linden"). Optional - a null source leaves
    # Contact.source unset on auto-create.
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    # The Contact column an ingested event's identity_source_path resolves onto
    # (external_id or email) - names which contact an event belongs to. Both
    # identity columns are optional at creation: an EventMapping can exist with
    # no identity configured yet, same as today's "tracked but no identity
    # mapping" state - ingestion still drops every event for it until set.
    identity_target_field: Mapped[str | None] = mapped_column(String, nullable=True)
    # Dot-path into event_data (e.g. "person.id") resolved at ingestion time to
    # find/create the Contact identified by identity_target_field. Set together
    # with identity_target_field, or not at all.
    identity_source_path: Mapped[str | None] = mapped_column(String, nullable=True)
    # Status stamped onto Contact.status for every contact auto-created while
    # ingesting this event_type - one of ContactStatus's values (see
    # app.schemas.contact). Applied only at creation, never on an
    # already-resolved contact (see get_or_create_from_event). Null means "use
    # Contact.status's own default (active)". See
    # docs/prds/0005-contact-status-and-event-mapping-defaults.md.
    default_status: Mapped[str | None] = mapped_column(String, nullable=True)
    # Tag names stamped onto every contact auto-created while ingesting this
    # event_type, via the same TagRepository.set_contact_tags write path
    # manual tagging uses. Applied only at creation, same as default_status.
    # Null/empty means no tags are applied.
    default_tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    # Null for host API calls, set to the operator's user id when created through
    # the UI - mirrors EventFieldMapping.created_by_id.
    created_by_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    field_mappings = relationship(
        "EventFieldMapping", back_populates="event_mapping", lazy="select"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.mixins import TimestampMixin
from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
import uuid

from app.db import Base


class ContactCustomFieldValue(Base, TimestampMixin):
    """A contact's current value for one CustomFieldDefinition. Current-state data, not
    a log - writing again overwrites the existing row rather than appending. No
    SoftDeleteMixin: a value represents current state, so deleting one is a hard delete
    (distinct from soft-deleting the definition itself). See
    docs/prds/0002-contact-custom-fields-and-events.md.
    """

    __tablename__ = "contact_custom_field_values"
    __table_args__ = (
        UniqueConstraint(
            "contact_id",
            "field_definition_id",
            name="uq_contact_custom_field_values_contact_field",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contact_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    field_definition_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("custom_field_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Validated against the field definition's value_type on every write (see
    # app.repositories.contact_custom_field_value_repository).
    value: Mapped[dict | list | str | float | bool] = mapped_column(
        JSONB, nullable=False
    )
    # The authenticated caller's user id at write time (request.state.user.id) - whether
    # that request came in via API key or JWT. No host-vs-operator distinction (see PRD).
    # Nullable: a value written by an EventFieldMapping during NATS event ingestion has
    # no authenticated caller - NULL there means "written by event-mapping ingestion",
    # distinguishable from any real user id in the "who/what last set this" read.
    set_by_user_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    field_definition = relationship("CustomFieldDefinition", lazy="joined")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def field_name(self) -> str:
        """The owning field definition's name - denormalized for the read schema."""
        return self.field_definition.name

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.event_field_mapping import EventFieldMapping
from app.models.event_mapping import IDENTITY_KEY_TARGETS, EventMapping
from app.repositories.soft_delete_repository import SoftDeleteRepository
from app.schemas.event_mapping import EventMappingCreate, EventMappingUpdateRequest


class EventMappingConflictError(ValueError):
    """Raised when an event_type collides with an existing active EventMapping."""


class InvalidEventMappingError(ValueError):
    """Raised when identity_target_field isn't one of IDENTITY_KEY_TARGETS."""


def _validate_identity_target_field(identity_target_field: Optional[str]) -> None:
    if identity_target_field is not None and identity_target_field not in (
        IDENTITY_KEY_TARGETS
    ):
        raise InvalidEventMappingError(
            "identity_target_field must be one of "
            f"{sorted(IDENTITY_KEY_TARGETS)}, got {identity_target_field!r}"
        )


class EventMappingRepository(SoftDeleteRepository[EventMapping]):
    """Repository for EventMapping CRUD - the parent registration of an
    event_type, its provenance, and its identity configuration. Replaces
    TrackedEventTypeRepository; see docs/prds/0004-event-mapping-consolidation.md.
    """

    def __init__(self, db: Session):
        super().__init__(db, EventMapping)

    def get_event_mapping(self, event_mapping_id: UUID) -> Optional[EventMapping]:
        """Get a single active EventMapping by ID."""
        return (
            self.db.query(EventMapping)
            .filter(EventMapping.id == event_mapping_id)
            .first()
        )

    def get_by_event_type(self, event_type: str) -> Optional[EventMapping]:
        """Get a single active EventMapping by its exact event_type - called on
        every ingested NATS message (see app.tasks.process_nats_event_task). No
        row for this event_type is the "untracked, drop it" case."""
        return (
            self.db.query(EventMapping)
            .filter(EventMapping.event_type == event_type)
            .first()
        )

    def get_event_mappings_query(self):
        """Get a query for all active EventMapping rows, for pagination."""
        return self.db.query(EventMapping).order_by(EventMapping.created_at.desc())

    def create_event_mapping(self, event_mapping: EventMappingCreate) -> EventMapping:
        """Register a new event_type, optionally with its identity configuration.

        Raises:
            EventMappingConflictError: the event_type is already registered by
                another active row.
            InvalidEventMappingError: identity_target_field isn't a recognized
                identity-eligible Contact column.
        """
        _validate_identity_target_field(event_mapping.identity_target_field)

        db_event_mapping = EventMapping(
            event_type=event_mapping.event_type,
            source=event_mapping.source,
            identity_target_field=event_mapping.identity_target_field,
            identity_source_path=event_mapping.identity_source_path,
            created_by_id=event_mapping.created_by_id,
        )
        self.db.add(db_event_mapping)
        try:
            self.db.commit()
        except IntegrityError as e:
            self.db.rollback()
            raise EventMappingConflictError(
                f"Event type {event_mapping.event_type!r} is already registered"
            ) from e
        self.db.refresh(db_event_mapping)
        return db_event_mapping

    def update_event_mapping(
        self, event_mapping_id: UUID, update: EventMappingUpdateRequest
    ) -> Optional[EventMapping]:
        """Update an EventMapping's source/identity configuration in place.

        Raises:
            InvalidEventMappingError: the resulting identity_target_field isn't a
                recognized identity-eligible Contact column.

        Returns:
            The updated EventMapping, or None if no active row matches the id.
        """
        db_event_mapping = self.get_event_mapping(event_mapping_id)
        if not db_event_mapping:
            return None

        update_data = update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_event_mapping, field, value)

        _validate_identity_target_field(db_event_mapping.identity_target_field)

        self.db.commit()
        self.db.refresh(db_event_mapping)
        return db_event_mapping

    def delete_event_mapping(self, event_mapping_id: UUID) -> bool:
        """Soft delete an EventMapping and cascade the soft-delete to all of its
        currently active EventFieldMapping children. Newly ingested events of
        this type stop being processed without a separate cleanup step."""
        if not self.delete_record(event_mapping_id):
            return False

        children = (
            self.db.query(EventFieldMapping)
            .filter(EventFieldMapping.event_mapping_id == event_mapping_id)
            .all()
        )
        now = datetime.now(timezone.utc)
        for child in children:
            child.deleted_at = now
        self.db.commit()
        return True

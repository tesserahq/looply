from typing import Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.tracked_event_type import TrackedEventType
from app.repositories.soft_delete_repository import SoftDeleteRepository
from app.schemas.tracked_event_type import TrackedEventTypeCreate


class TrackedEventTypeConflictError(ValueError):
    """Raised when an event_type collides with an existing active registration."""


class TrackedEventTypeRepository(SoftDeleteRepository[TrackedEventType]):
    """Repository for the TrackedEventType allow-list. Immutable once created -
    there is no update method; delete and recreate to change event_type.
    """

    def __init__(self, db: Session):
        super().__init__(db, TrackedEventType)

    def get_tracked_event_type(self, tracked_id: UUID) -> Optional[TrackedEventType]:
        """Get a single active registration by ID."""
        return (
            self.db.query(TrackedEventType)
            .filter(TrackedEventType.id == tracked_id)
            .first()
        )

    def get_by_event_type(self, event_type: str) -> Optional[TrackedEventType]:
        """Get a single active registration by its exact event_type - called on
        every ingested NATS message (see app.tasks.process_nats_event_task)."""
        return (
            self.db.query(TrackedEventType)
            .filter(TrackedEventType.event_type == event_type)
            .first()
        )

    def get_tracked_event_types_query(self):
        """Get a query for all active registrations, for pagination."""
        return self.db.query(TrackedEventType).order_by(
            TrackedEventType.created_at.desc()
        )

    def create_tracked_event_type(
        self, tracked: TrackedEventTypeCreate
    ) -> TrackedEventType:
        """
        Register a new event_type to track.

        Raises:
            TrackedEventTypeConflictError: the event_type is already registered by
                another active row.
        """
        db_tracked = TrackedEventType(
            event_type=tracked.event_type,
            created_by_id=tracked.created_by_id,
        )
        self.db.add(db_tracked)
        try:
            self.db.commit()
        except IntegrityError as e:
            self.db.rollback()
            raise TrackedEventTypeConflictError(
                f"Event type {tracked.event_type!r} is already tracked"
            ) from e
        self.db.refresh(db_tracked)
        return db_tracked

    def delete_tracked_event_type(self, tracked_id: UUID) -> bool:
        """Soft delete a registration. Newly ingested events of this type stop
        being processed without a separate cleanup step."""
        return self.delete_record(tracked_id)

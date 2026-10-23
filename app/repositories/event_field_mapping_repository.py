from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.event_field_mapping import CONTACT_FIELD_TARGETS, EventFieldMapping
from app.repositories.soft_delete_repository import SoftDeleteRepository
from app.schemas.event_field_mapping import (
    EventFieldMappingCreate,
    EventFieldMappingTargetType,
)


class InvalidEventFieldMappingError(ValueError):
    """Raised when a mapping's target_type/target_field shape is invalid - e.g.
    an unrecognized target_field."""


def _validate_target_shape(
    target_type: EventFieldMappingTargetType, target_field: Optional[str]
) -> None:
    if (
        target_type == EventFieldMappingTargetType.CONTACT_FIELD
        and target_field not in CONTACT_FIELD_TARGETS
    ):
        raise InvalidEventFieldMappingError(
            f"{target_field!r} is not a recognized Contact field"
        )


class EventFieldMappingRepository(SoftDeleteRepository[EventFieldMapping]):
    """Repository for EventFieldMapping CRUD - the non-identity attribute
    children of an EventMapping. Editable in place; see
    docs/prds/0004-event-mapping-consolidation.md.
    """

    def __init__(self, db: Session):
        super().__init__(db, EventFieldMapping)

    def get_mapping(self, mapping_id: UUID) -> Optional[EventFieldMapping]:
        """Get a single active mapping by ID."""
        return (
            self.db.query(EventFieldMapping)
            .filter(EventFieldMapping.id == mapping_id)
            .first()
        )

    def get_mappings_query(self, event_mapping_id: Optional[UUID] = None):
        """Get a query for active mappings, for pagination - scoped to a single
        parent EventMapping when event_mapping_id is given, all active mappings
        otherwise."""
        query = self.db.query(EventFieldMapping)
        if event_mapping_id is not None:
            query = query.filter(EventFieldMapping.event_mapping_id == event_mapping_id)
        return query.order_by(EventFieldMapping.created_at.desc())

    def get_mappings_for_event_mapping(
        self, event_mapping_id: UUID
    ) -> List[EventFieldMapping]:
        """Get all active attribute mappings for a given parent EventMapping -
        called during NATS event ingestion (see
        app.tasks.process_nats_event_task)."""
        return (
            self.db.query(EventFieldMapping)
            .filter(EventFieldMapping.event_mapping_id == event_mapping_id)
            .all()
        )

    def create_mapping(self, mapping: EventFieldMappingCreate) -> EventFieldMapping:
        """Create a new attribute mapping under its parent EventMapping.

        Raises:
            InvalidEventFieldMappingError: target_field isn't a recognized
                Contact column.
        """
        _validate_target_shape(mapping.target_type, mapping.target_field)

        db_mapping = EventFieldMapping(
            event_mapping_id=mapping.event_mapping_id,
            source_path=mapping.source_path,
            target_type=mapping.target_type.value,
            target_field=mapping.target_field,
            field_definition_id=mapping.field_definition_id,
            created_by_id=mapping.created_by_id,
        )
        self.db.add(db_mapping)
        self.db.flush()
        self.db.refresh(db_mapping)
        return db_mapping

    def update_mapping(
        self,
        mapping_id: UUID,
        *,
        source_path: Optional[str] = None,
        target_type: Optional[EventFieldMappingTargetType] = None,
        target_field: Optional[str] = None,
        field_definition_id: Optional[UUID] = None,
        clear_target_field: bool = False,
        clear_field_definition_id: bool = False,
    ) -> Optional[EventFieldMapping]:
        """Update an attribute mapping's fields in place, re-validating the
        resulting shape the same way create does.

        Raises:
            InvalidEventFieldMappingError: the resulting target_field isn't a
                recognized Contact column.

        Returns:
            The updated mapping, or None if no active row matches mapping_id.
        """
        db_mapping = self.get_mapping(mapping_id)
        if not db_mapping:
            return None

        if source_path is not None:
            db_mapping.source_path = source_path
        if target_type is not None:
            db_mapping.target_type = target_type.value
        if target_field is not None:
            db_mapping.target_field = target_field
        elif clear_target_field:
            db_mapping.target_field = None
        if field_definition_id is not None:
            db_mapping.field_definition_id = field_definition_id
        elif clear_field_definition_id:
            db_mapping.field_definition_id = None

        _validate_target_shape(
            EventFieldMappingTargetType(db_mapping.target_type), db_mapping.target_field
        )

        self.db.flush()
        self.db.refresh(db_mapping)
        return db_mapping

    def delete_mapping(self, mapping_id: UUID) -> bool:
        """Soft delete a mapping. It stops being applied to newly ingested events
        without a separate cleanup step."""
        return self.delete_record(mapping_id)

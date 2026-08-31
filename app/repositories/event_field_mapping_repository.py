from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.event_field_mapping import EventFieldMapping
from app.repositories.soft_delete_repository import SoftDeleteRepository
from app.schemas.event_field_mapping import EventFieldMappingCreate


class EventFieldMappingRepository(SoftDeleteRepository[EventFieldMapping]):
    """Repository for EventFieldMapping CRUD. Immutable once created - there is no
    update method; delete and recreate to change event_type, source_path, or the
    target field (see the model docstring).
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

    def get_mappings_query(self):
        """Get a query for all active mappings, for pagination."""
        return self.db.query(EventFieldMapping).order_by(
            EventFieldMapping.created_at.desc()
        )

    def get_mappings_for_event_type(self, event_type: str) -> List[EventFieldMapping]:
        """Get all active mappings that apply to a given event_type - called during
        NATS event ingestion (see app.tasks.process_nats_event_task)."""
        return (
            self.db.query(EventFieldMapping)
            .filter(EventFieldMapping.event_type == event_type)
            .all()
        )

    def create_mapping(self, mapping: EventFieldMappingCreate) -> EventFieldMapping:
        """Create a new event-to-field mapping."""
        db_mapping = EventFieldMapping(
            event_type=mapping.event_type,
            source_path=mapping.source_path,
            field_definition_id=mapping.field_definition_id,
            created_by_id=mapping.created_by_id,
        )
        self.db.add(db_mapping)
        self.db.commit()
        self.db.refresh(db_mapping)
        return db_mapping

    def delete_mapping(self, mapping_id: UUID) -> bool:
        """Soft delete a mapping. It stops being applied to newly ingested events
        without a separate cleanup step."""
        return self.delete_record(mapping_id)

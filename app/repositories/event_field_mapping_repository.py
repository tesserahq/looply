from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.event_field_mapping import (
    CONTACT_FIELD_TARGETS,
    IDENTITY_KEY_TARGETS,
    EventFieldMapping,
)
from app.repositories.soft_delete_repository import SoftDeleteRepository
from app.schemas.event_field_mapping import (
    EventFieldMappingCreate,
    EventFieldMappingTargetType,
)


class InvalidEventFieldMappingError(ValueError):
    """Raised when a mapping's target_type/target_field/is_identity_key shape is
    invalid - e.g. an unrecognized target_field, or is_identity_key targeting a
    field with no uniqueness guarantee."""


class DuplicateIdentityKeyError(ValueError):
    """Raised when creating a second is_identity_key=True mapping for an
    event_type that already has one active."""


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
        """Create a new event-to-field mapping.

        Raises:
            InvalidEventFieldMappingError: target_field isn't a recognized Contact
                column, or is_identity_key is set for a target_field with no
                uniqueness guarantee (only "external_id"/"email" qualify).
            DuplicateIdentityKeyError: event_type already has an active
                is_identity_key=True mapping.
        """
        if mapping.target_type == EventFieldMappingTargetType.CONTACT_FIELD:
            if mapping.target_field not in CONTACT_FIELD_TARGETS:
                raise InvalidEventFieldMappingError(
                    f"{mapping.target_field!r} is not a recognized Contact field"
                )
            if mapping.is_identity_key and mapping.target_field not in IDENTITY_KEY_TARGETS:
                raise InvalidEventFieldMappingError(
                    "is_identity_key mappings must target one of "
                    f"{sorted(IDENTITY_KEY_TARGETS)}, got {mapping.target_field!r}"
                )

        if mapping.is_identity_key:
            existing = (
                self.db.query(EventFieldMapping)
                .filter(
                    EventFieldMapping.event_type == mapping.event_type,
                    EventFieldMapping.is_identity_key.is_(True),
                )
                .first()
            )
            if existing:
                raise DuplicateIdentityKeyError(
                    f"Event type {mapping.event_type!r} already has an identity-key "
                    "mapping"
                )

        db_mapping = EventFieldMapping(
            event_type=mapping.event_type,
            source_path=mapping.source_path,
            target_type=mapping.target_type.value,
            target_field=mapping.target_field,
            field_definition_id=mapping.field_definition_id,
            is_identity_key=mapping.is_identity_key,
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

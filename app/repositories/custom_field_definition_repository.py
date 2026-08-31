from typing import Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.custom_field_definition import CustomFieldDefinition
from app.repositories.soft_delete_repository import SoftDeleteRepository
from app.schemas.custom_field_definition import CustomFieldDefinitionCreate


class CustomFieldDefinitionNameConflictError(ValueError):
    """Raised when a field definition's name collides with an existing active one."""


class CustomFieldDefinitionRepository(SoftDeleteRepository[CustomFieldDefinition]):
    """Repository class for managing CustomFieldDefinition CRUD.

    name and value_type are immutable once set - there is no update method; a
    definition must be soft-deleted and recreated instead (see the PRD).
    """

    def __init__(self, db: Session):
        super().__init__(db, CustomFieldDefinition)

    def get_definition(self, definition_id: UUID) -> Optional[CustomFieldDefinition]:
        """Get a single active field definition by ID."""
        return (
            self.db.query(CustomFieldDefinition)
            .filter(CustomFieldDefinition.id == definition_id)
            .first()
        )

    def get_definition_by_name(self, name: str) -> Optional[CustomFieldDefinition]:
        """Get a single active field definition by its case-insensitive name."""
        return (
            self.db.query(CustomFieldDefinition)
            .filter(func.lower(CustomFieldDefinition.name) == name.lower())
            .first()
        )

    def get_definitions_query(self):
        """Get a query for all active field definitions, for pagination."""
        return self.db.query(CustomFieldDefinition).order_by(
            CustomFieldDefinition.created_at.desc()
        )

    def create_definition(
        self, definition: CustomFieldDefinitionCreate
    ) -> CustomFieldDefinition:
        """
        Create a new field definition.

        Raises:
            CustomFieldDefinitionNameConflictError: the name is already taken by
                another active definition (case-insensitive).
        """
        db_definition = CustomFieldDefinition(
            name=definition.name,
            value_type=definition.value_type.value,
            label=definition.label,
            created_by_id=definition.created_by_id,
        )
        self.db.add(db_definition)
        try:
            self.db.commit()
        except IntegrityError as e:
            self.db.rollback()
            raise CustomFieldDefinitionNameConflictError(
                f"A custom field named {definition.name!r} already exists"
            ) from e
        self.db.refresh(db_definition)
        return db_definition

    def delete_definition(self, definition_id: UUID) -> bool:
        """Soft delete a field definition. Its values become unreachable through the
        normal (active-only) query path without a separate cleanup step, thanks to the
        global soft-delete filter (see app.db)."""
        return self.delete_record(definition_id)

from datetime import date
from typing import List, Optional, Union
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.contact_custom_field_value import ContactCustomFieldValue
from app.models.custom_field_definition import CustomFieldDefinition
from app.schemas.custom_field_definition import FieldValueType


class UndefinedCustomFieldError(ValueError):
    """Raised when writing to a field_name with no active CustomFieldDefinition."""


class CustomFieldValueTypeError(ValueError):
    """Raised when a value doesn't match its field definition's locked value_type."""


def _validate_value_type(value: Union[str, float, bool], value_type: str) -> None:
    """
    Validate a raw value against a field definition's locked value_type.

    Raises:
        CustomFieldValueTypeError: the value doesn't match the expected type.
    """
    if value_type == FieldValueType.BOOLEAN.value:
        if not isinstance(value, bool):
            raise CustomFieldValueTypeError("Expected a boolean value")
    elif value_type == FieldValueType.NUMBER.value:
        # bool is a subclass of int in Python - exclude it explicitly so a bool
        # value doesn't silently pass as a number.
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise CustomFieldValueTypeError("Expected a numeric value")
    elif value_type == FieldValueType.DATE.value:
        if not isinstance(value, str):
            raise CustomFieldValueTypeError(
                'Expected a date-only ISO 8601 string (e.g. "2026-08-30")'
            )
        try:
            date.fromisoformat(value)
        except ValueError:
            raise CustomFieldValueTypeError(
                'Expected a date-only ISO 8601 string (e.g. "2026-08-30")'
            )
    else:  # FieldValueType.STRING
        if not isinstance(value, str):
            raise CustomFieldValueTypeError("Expected a string value")


class ContactCustomFieldValueRepository:
    """Repository holding the type-locking business logic for a contact's custom
    field values - the module most worth getting right per the PRD's Testing
    Decisions, since it's what makes a bad host-side write fail loudly (422) rather
    than silently corrupting segment results.
    """

    def __init__(self, db: Session):
        self.db = db

    def set_value(
        self,
        contact_id: UUID,
        field_name: str,
        value: Union[str, float, bool],
        set_by_user_id: UUID,
    ) -> ContactCustomFieldValue:
        """
        Upsert a contact's value for a named field - one current value per contact
        per field; writing again overwrites, it does not append.

        Raises:
            UndefinedCustomFieldError: no active definition exists for field_name.
            CustomFieldValueTypeError: value doesn't match the definition's value_type.
        """
        definition = (
            self.db.query(CustomFieldDefinition)
            .filter(func.lower(CustomFieldDefinition.name) == field_name.lower())
            .first()
        )
        if not definition:
            raise UndefinedCustomFieldError(
                f"No custom field definition named {field_name!r} exists"
            )

        _validate_value_type(value, definition.value_type)

        existing = (
            self.db.query(ContactCustomFieldValue)
            .filter(
                ContactCustomFieldValue.contact_id == contact_id,
                ContactCustomFieldValue.field_definition_id == definition.id,
            )
            .first()
        )

        if existing:
            existing.value = value
            existing.set_by_user_id = set_by_user_id
            self.db.commit()
            self.db.refresh(existing)
            return existing

        new_value = ContactCustomFieldValue(
            contact_id=contact_id,
            field_definition_id=definition.id,
            value=value,
            set_by_user_id=set_by_user_id,
        )
        self.db.add(new_value)
        self.db.commit()
        self.db.refresh(new_value)
        return new_value

    def list_values_for_contact(
        self, contact_id: UUID
    ) -> List[ContactCustomFieldValue]:
        """List a contact's current custom field values."""
        return (
            self.db.query(ContactCustomFieldValue)
            .join(CustomFieldDefinition)
            .filter(ContactCustomFieldValue.contact_id == contact_id)
            .order_by(CustomFieldDefinition.name)
            .all()
        )

    def get_value_by_field_name(
        self, contact_id: UUID, field_name: str
    ) -> Optional[ContactCustomFieldValue]:
        """Get a contact's current value for a named field, if any."""
        return (
            self.db.query(ContactCustomFieldValue)
            .join(CustomFieldDefinition)
            .filter(
                ContactCustomFieldValue.contact_id == contact_id,
                func.lower(CustomFieldDefinition.name) == field_name.lower(),
            )
            .first()
        )

    def delete_value(self, contact_id: UUID, field_name: str) -> bool:
        """Hard delete a contact's value for a named field - current-state data,
        not a log, so this is a real delete (see ContactCustomFieldValue)."""
        value = self.get_value_by_field_name(contact_id, field_name)
        if not value:
            return False
        self.db.delete(value)
        self.db.commit()
        return True

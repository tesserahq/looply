from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime
from enum import Enum


class FieldValueType(str, Enum):
    """Fixed set of value types a CustomFieldDefinition can declare. Required at
    creation, never inferred from a value - see docs/prds/0002-contact-custom-fields-and-events.md.
    """

    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"


class CustomFieldDefinitionCreateRequest(BaseModel):
    """Schema for creating a new custom field definition."""

    name: str
    """Machine name, unique (case-insensitive) across the deployment. Immutable once set."""

    value_type: FieldValueType
    """The type every value written under this field name must match. Immutable once set."""

    label: Optional[str] = None
    """Optional human-readable display name, separate from the machine name."""


class CustomFieldDefinitionCreate(CustomFieldDefinitionCreateRequest):
    """Internal create schema, with created_by_id injected (null for host API calls)."""

    created_by_id: Optional[UUID] = None


class CustomFieldDefinition(BaseModel):
    """Schema for a custom field definition returned in API responses."""

    id: UUID
    name: str
    value_type: FieldValueType
    label: Optional[str] = None
    created_by_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

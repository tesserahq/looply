from pydantic import BaseModel
from typing import Optional, Union
from uuid import UUID
from datetime import datetime


class ContactCustomFieldValueWrite(BaseModel):
    """Request body for PUT /contacts/{external_id}/custom-fields/{field_name}."""

    value: Union[str, float, bool]
    """The value to set. Validated against the field definition's value_type on write -
    a NUMBER as a JSON number, a BOOLEAN as a JSON bool, a STRING/DATE as a string (a DATE
    value is a date-only ISO 8601 string, e.g. "2026-08-30")."""


class ContactCustomFieldValue(BaseModel):
    """Schema for a contact's current custom field value, returned in API responses."""

    id: UUID
    field_definition_id: UUID
    field_name: str
    """The owning field definition's name, denormalized for display convenience."""

    value: Union[str, float, bool]
    set_by_user_id: Optional[UUID] = None
    """Null if this value was written by an EventFieldMapping during NATS event
    ingestion rather than an authenticated caller."""
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContactCustomFieldValueCreate(BaseModel):
    """Internal create/upsert schema."""

    contact_id: UUID
    field_definition_id: UUID
    value: Union[str, float, bool]
    set_by_user_id: Optional[UUID] = None

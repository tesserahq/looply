from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime


class EventFieldMappingCreateRequest(BaseModel):
    """Schema for creating a new event-to-field mapping."""

    event_type: str
    """Exact-match event_type this mapping applies to (e.g. "com.mylinden.person.created")."""

    source_path: str
    """Dot-path into the envelope's event_data (e.g. "account.family_member_count")."""

    field_name: str
    """The target CustomFieldDefinition's name - must already exist (422 otherwise),
    same as writing a custom field value directly."""


class EventFieldMappingCreate(BaseModel):
    """Internal create schema, with field_name resolved to field_definition_id and
    created_by_id injected (null for host API calls)."""

    event_type: str
    source_path: str
    field_definition_id: UUID
    created_by_id: Optional[UUID] = None


class EventFieldMapping(BaseModel):
    """Schema for an event-to-field mapping returned in API responses."""

    id: UUID
    event_type: str
    source_path: str
    field_definition_id: UUID
    field_name: str
    """The target field definition's name, denormalized for display convenience."""
    created_by_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

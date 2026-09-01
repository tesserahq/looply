from pydantic import BaseModel, model_validator
from typing import Optional
from uuid import UUID
from datetime import datetime
from enum import Enum


class EventFieldMappingTargetType(str, Enum):
    """Whether a mapping writes onto a built-in Contact column or a custom field."""

    CONTACT_FIELD = "contact_field"
    CUSTOM_FIELD = "custom_field"


class EventFieldMappingCreateRequest(BaseModel):
    """Schema for creating a new attribute mapping under an EventMapping. Posted
    to /event-mappings/{event_mapping_id}/fields - event_type is implied by the
    URL, not part of this payload."""

    source_path: str
    """Dot-path into the envelope's event_data (e.g. "person.account.family_member_count")."""

    target_type: EventFieldMappingTargetType = EventFieldMappingTargetType.CUSTOM_FIELD
    """Whether this mapping targets a built-in Contact column ("contact_field") or a
    custom field ("custom_field"). Defaults to "custom_field" for backwards
    compatibility with callers written against the pre-0003 API shape."""

    target_field: Optional[str] = None
    """The Contact column to write to - required (and only meaningful) when
    target_type="contact_field". Validated against a fixed allow-list of real
    Contact columns (422 otherwise)."""

    field_name: Optional[str] = None
    """The target CustomFieldDefinition's name - required (and only meaningful) when
    target_type="custom_field". Must already exist (422 otherwise), same as writing
    a custom field value directly."""

    @model_validator(mode="after")
    def _validate_target_shape(self) -> "EventFieldMappingCreateRequest":
        if self.target_type == EventFieldMappingTargetType.CONTACT_FIELD:
            if not self.target_field:
                raise ValueError(
                    'target_field is required when target_type="contact_field"'
                )
            if self.field_name:
                raise ValueError(
                    'field_name must not be set when target_type="contact_field"'
                )
        else:
            if not self.field_name:
                raise ValueError(
                    'field_name is required when target_type="custom_field"'
                )
            if self.target_field:
                raise ValueError(
                    'target_field must not be set when target_type="custom_field"'
                )
        return self


class EventFieldMappingUpdateRequest(BaseModel):
    """Schema for updating an existing attribute mapping in place. All fields
    optional; only provided fields change. The resulting shape (after merging
    with the existing row) is validated the same way create is."""

    source_path: Optional[str] = None
    target_type: Optional[EventFieldMappingTargetType] = None
    target_field: Optional[str] = None
    field_name: Optional[str] = None


class EventFieldMappingCreate(BaseModel):
    """Internal create schema, with field_name resolved to field_definition_id and
    created_by_id injected (null for host API calls)."""

    event_mapping_id: UUID
    source_path: str
    target_type: EventFieldMappingTargetType = EventFieldMappingTargetType.CUSTOM_FIELD
    target_field: Optional[str] = None
    field_definition_id: Optional[UUID] = None
    created_by_id: Optional[UUID] = None


class EventFieldMapping(BaseModel):
    """Schema for an event-to-field mapping returned in API responses."""

    id: UUID
    event_mapping_id: UUID
    source_path: str
    target_type: EventFieldMappingTargetType
    target_field: Optional[str] = None
    field_definition_id: Optional[UUID] = None
    field_name: Optional[str] = None
    """The target field definition's name, denormalized for display convenience.
    None for a contact_field mapping."""
    created_by_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

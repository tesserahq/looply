from pydantic import BaseModel, model_validator
from typing import Optional
from uuid import UUID
from datetime import datetime


class EventMappingCreateRequest(BaseModel):
    """Schema for registering a new event_type to act on."""

    event_type: str
    """Exact-match event_type to start acting on (e.g. "com.mylinden.person.created").
    Unique across the deployment (active rows only)."""

    source: Optional[str] = None
    """Stamped onto Contact.source for every contact auto-created while ingesting
    this event_type (e.g. "linden"). Optional - a null source leaves
    Contact.source unset on auto-create."""

    identity_target_field: Optional[str] = None
    """The Contact column ("external_id" or "email") an ingested event's
    identity_source_path resolves onto - names which contact an event belongs
    to. Optional at creation; without it, this event_type is registered but
    every event for it is dropped until identity is configured (via create or a
    later update)."""

    identity_source_path: Optional[str] = None
    """Dot-path into event_data (e.g. "person.id") resolved to find/create the
    Contact identified by identity_target_field. Required together with
    identity_target_field, or omitted together with it."""

    @model_validator(mode="after")
    def _validate_identity_shape(self) -> "EventMappingCreateRequest":
        if bool(self.identity_target_field) != bool(self.identity_source_path):
            raise ValueError(
                "identity_target_field and identity_source_path must be set together"
            )
        return self


class EventMappingUpdateRequest(BaseModel):
    """Schema for updating an existing event mapping's source/identity
    configuration in place. All fields optional; only provided fields change."""

    source: Optional[str] = None
    identity_target_field: Optional[str] = None
    identity_source_path: Optional[str] = None

    @model_validator(mode="after")
    def _validate_identity_shape(self) -> "EventMappingUpdateRequest":
        if bool(self.identity_target_field) != bool(self.identity_source_path):
            raise ValueError(
                "identity_target_field and identity_source_path must be set together"
            )
        return self


class EventMappingCreate(BaseModel):
    """Internal create schema, with created_by_id injected (null for host API
    calls)."""

    event_type: str
    source: Optional[str] = None
    identity_target_field: Optional[str] = None
    identity_source_path: Optional[str] = None
    created_by_id: Optional[UUID] = None


class EventMapping(BaseModel):
    """Schema for an event mapping returned in API responses."""

    id: UUID
    event_type: str
    source: Optional[str] = None
    identity_target_field: Optional[str] = None
    identity_source_path: Optional[str] = None
    created_by_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

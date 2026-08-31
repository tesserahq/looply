from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime


class TrackedEventTypeCreateRequest(BaseModel):
    """Schema for registering a new event_type to track."""

    event_type: str
    """Exact-match event_type to start acting on (e.g. "com.mylinden.person.created").
    Unique across the deployment (active rows only). Immutable once set."""

    source: Optional[str] = None
    """Stamped onto Contact.source for every contact auto-created while ingesting
    this event_type (e.g. "linden"). Optional - a null source leaves
    Contact.source unset on auto-create."""


class TrackedEventTypeCreate(TrackedEventTypeCreateRequest):
    """Internal create schema, with created_by_id injected (null for host API calls)."""

    created_by_id: Optional[UUID] = None


class TrackedEventType(BaseModel):
    """Schema for a tracked event type returned in API responses."""

    id: UUID
    event_type: str
    source: Optional[str] = None
    created_by_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class TagCreateRequest(BaseModel):
    """Schema for creating a new tag."""

    name: str
    """Tag name. Unique across the deployment (case-insensitive, active rows only)."""


class TagUpdate(BaseModel):
    """Schema for renaming an existing tag."""

    name: str
    """New tag name. Must not collide with another active tag (case-insensitive)."""


class Tag(BaseModel):
    """Schema for a tag returned in API responses."""

    id: UUID
    name: str
    created_by_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TagWithCounts(Tag):
    """A tag plus how many contacts/campaigns it's currently assigned to -
    used by GET /tags so the management list can show usage at a glance."""

    contacts_count: int
    campaigns_count: int


class TagUsageSegment(BaseModel):
    """A segment referenced in a TagUsage response."""

    id: UUID
    name: str

    model_config = {"from_attributes": True}


class TagUsage(BaseModel):
    """A tag's full impact if deleted: how many contacts/campaigns would
    lose the tag, and which saved segments would silently stop matching
    it. Fetched lazily by the delete-confirm dialog, not part of the list."""

    contacts_count: int
    campaigns_count: int
    segments: list[TagUsageSegment]

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

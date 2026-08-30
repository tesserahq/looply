from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime

from app.schemas.segment_rule import SegmentRuleCreate


class SegmentBase(BaseModel):
    """Base segment model containing common segment attributes."""

    id: Optional[UUID] = None
    """Unique identifier for the segment. Defaults to None."""

    name: str
    """Name of the segment. Unique across the account, not per-list."""

    rule: SegmentRuleCreate
    """The condition tree defining this segment's audience."""

    created_by_id: UUID
    """ID of the user who created this segment."""


class SegmentCreate(SegmentBase):
    """Schema for creating a new segment. Inherits all fields from SegmentBase."""

    pass


class SegmentCreateRequest(BaseModel):
    """Schema for creating a new segment without created_by_id (injected from current user)."""

    name: str
    """Name of the segment. Unique across the account, not per-list."""

    rule: SegmentRuleCreate
    """The condition tree defining this segment's audience."""


class SegmentUpdate(BaseModel):
    """Schema for updating an existing segment. All fields are optional."""

    name: Optional[str] = None
    """Updated name."""

    rule: Optional[SegmentRuleCreate] = None
    """Updated condition tree."""


class SegmentInDB(SegmentBase):
    """Schema representing a segment as stored in the database."""

    id: UUID
    """Unique identifier for the segment in the database."""

    created_at: datetime
    """Timestamp when the segment record was created."""

    updated_at: datetime
    """Timestamp when the segment record was last updated."""

    model_config = {"from_attributes": True}


class Segment(SegmentInDB):
    """Schema for segment data returned in API responses."""

    pass


class SegmentPreviewResponse(BaseModel):
    """Schema for a segment's live, non-persisted contact count."""

    contact_count: int
    """How many contacts this segment currently resolves to."""

from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class ContactInteractionBase(BaseModel):
    """Base contact interaction model containing common attributes."""

    id: Optional[UUID] = None
    """Unique identifier for the interaction. Defaults to None."""

    contact_id: UUID
    """ID of the contact this interaction is associated with."""

    note: str = Field(..., min_length=1, max_length=1000)
    """The interaction note text (typically 500-1000 characters)."""

    interaction_timestamp: datetime
    """Timestamp when the interaction actually occurred."""

    action: Optional[str] = None
    """Optional action item for follow-up (e.g., 'Follow up in 2 weeks', 'Send proposal')."""

    action_timestamp: Optional[datetime] = None
    """Optional timestamp for when the action should be taken."""

    created_by_id: UUID
    """ID of the user who created this interaction note."""


class ContactInteractionCreate(ContactInteractionBase):
    """Schema for creating a new contact interaction. Inherits all fields from ContactInteractionBase."""

    pass


class ContactInteractionCreateRequest(BaseModel):
    """Schema for creating a new contact interaction via API request.

    Note: contact_id comes from the URL path parameter and interaction_timestamp
    is set by the router (defaults to current time if not provided).
    """

    note: str = Field(..., min_length=1, max_length=1000)
    """The interaction note text (typically 500-1000 characters)."""

    interaction_timestamp: Optional[datetime] = None
    """Optional timestamp when the interaction actually occurred. Defaults to current time if not provided."""

    action: Optional[str] = None
    """Optional action item for follow-up (e.g., 'Follow up in 2 weeks', 'Send proposal')."""

    action_timestamp: Optional[datetime] = None
    """Optional timestamp for when the action should be taken."""


class ContactInteractionUpdate(BaseModel):
    """Schema for updating an existing contact interaction. All fields are optional."""

    note: Optional[str] = Field(None, min_length=1, max_length=1000)
    """Updated interaction note text."""

    interaction_timestamp: Optional[datetime] = None
    """Updated timestamp when the interaction occurred."""

    action: Optional[str] = None
    """Updated action item."""

    action_timestamp: Optional[datetime] = None
    """Updated action timestamp."""


class ContactInteractionInDB(ContactInteractionBase):
    """Schema representing a contact interaction as stored in the database. Includes database-specific fields."""

    id: UUID
    """Unique identifier for the interaction in the database."""

    created_at: datetime
    """Timestamp when the interaction record was created."""

    updated_at: datetime
    """Timestamp when the interaction record was last updated."""

    model_config = {"from_attributes": True}


class ContactInteraction(ContactInteractionInDB):
    """Schema for contact interaction data returned in API responses. Inherits all fields from ContactInteractionInDB."""

    pass

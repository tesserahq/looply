from pydantic import BaseModel, EmailStr
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from app.schemas.contact_interaction import ContactInteractionInDB


class ContactSummary(BaseModel):
    """Schema for contact summary information in stats."""

    id: UUID
    """Contact ID."""

    first_name: Optional[str] = None
    """Contact's first name."""

    last_name: Optional[str] = None
    """Contact's last name."""

    email: Optional[EmailStr] = None
    """Contact's email address."""

    created_at: datetime
    """Timestamp when the contact was created."""

    updated_at: datetime
    """Timestamp when the contact was last updated."""

    model_config = {"from_attributes": True}


class ContactInteractionWithContact(ContactInteractionInDB):
    """Schema for contact interaction with nested contact information."""

    contact: ContactSummary
    """Contact information associated with this interaction."""

    model_config = {"from_attributes": True}


class Stats(BaseModel):
    """Schema for statistics endpoint response."""

    total_contacts: int
    """Total number of contacts in the system."""

    total_list: int
    """Total number of contact lists in the system."""

    total_public_list: int
    """Total number of public contact lists."""

    total_private_list: int
    """Total number of private contact lists."""

    upcoming_interactions: List[ContactInteractionWithContact]
    """List of contact interactions with actions within the next 5 days."""

    recent_contacts: List[ContactSummary]
    """Last 5 contacts created in the system."""

    model_config = {"from_attributes": True}

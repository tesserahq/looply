"""Contact list member schemas."""

from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class ContactListMemberBase(BaseModel):
    """Base contact list member model."""

    contact_list_id: UUID
    """ID of the contact list."""

    contact_id: UUID
    """ID of the contact."""


class ContactListMemberInDB(ContactListMemberBase):
    """Schema representing a contact list member as stored in the database."""

    id: UUID
    """Unique identifier for the member record."""

    created_at: datetime
    """Timestamp when the member was added."""

    updated_at: datetime
    """Timestamp when the member was last updated."""

    model_config = {"from_attributes": True}


class ContactListMember(ContactListMemberInDB):
    """Schema for contact list member data returned in API responses."""

    pass

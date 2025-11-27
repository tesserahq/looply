from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime

from app.schemas.contact import Contact


class ContactListBase(BaseModel):
    """Base contact list model containing common contact list attributes."""

    id: Optional[UUID] = None
    """Unique identifier for the contact list. Defaults to None."""

    name: str
    """Name of the contact list. Required field."""

    description: Optional[str] = None
    """Description of the contact list. Optional field."""

    is_public: bool = False
    """Whether the contact list is public. Defaults to False."""

    created_by_id: UUID
    """ID of the user who created this contact list. Required field."""


class ContactListCreate(ContactListBase):
    """Schema for creating a new contact list. Inherits all fields from ContactListBase."""

    pass


class ContactListCreateRequest(BaseModel):
    """Schema for creating a new contact list without created_by_id (injected from current user)."""

    name: str
    """Name of the contact list. Required field."""

    description: Optional[str] = None
    """Description of the contact list. Optional field."""

    is_public: bool = False
    """Whether the contact list is public. Defaults to False."""


class ContactListUpdate(BaseModel):
    """Schema for updating an existing contact list. All fields are optional."""

    name: Optional[str] = None
    """Updated name."""

    description: Optional[str] = None
    """Updated description."""

    is_public: Optional[bool] = None


class ContactListInDB(ContactListBase):
    """Schema representing a contact list as stored in the database. Includes database-specific fields."""

    id: UUID
    """Unique identifier for the contact list in the database."""

    created_at: datetime
    """Timestamp when the contact list record was created."""

    updated_at: datetime
    """Timestamp when the contact list record was last updated."""

    model_config = {"from_attributes": True}


class ContactList(ContactListInDB):
    """Schema for contact list data returned in API responses. Inherits all fields from ContactListInDB."""

    pass


class AddMembersRequest(BaseModel):
    """Schema for adding members to a contact list."""

    contact_ids: list[UUID]
    """List of contact IDs to add to the list."""


class MemberCountResponse(BaseModel):
    """Schema for contact list member count response."""

    contact_list_id: UUID
    """ID of the contact list."""

    count: int
    """Number of active members in the list."""


class ListMembersResponse(BaseModel):
    """Schema for listing contact list members."""

    contact_list_id: UUID
    """ID of the contact list."""

    members: list[Contact]
    """List of contacts in the contact list."""

    model_config = {"from_attributes": True}

from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime

from app.schemas.contact import Contact


class WaitingListBase(BaseModel):
    """Base waiting list model containing common waiting list attributes."""

    id: Optional[UUID] = None
    """Unique identifier for the waiting list. Defaults to None."""

    name: str
    """Name of the waiting list. Required field."""

    description: Optional[str] = None
    """Description of the waiting list. Optional field."""

    created_by_id: UUID
    """ID of the user who created this waiting list. Required field."""


class WaitingListCreate(WaitingListBase):
    """Schema for creating a new waiting list. Inherits all fields from WaitingListBase."""

    pass


class WaitingListCreateRequest(BaseModel):
    """Schema for creating a new waiting list without created_by_id (injected from current user)."""

    name: str
    """Name of the waiting list. Required field."""

    description: Optional[str] = None
    """Description of the waiting list. Optional field."""


class WaitingListUpdate(BaseModel):
    """Schema for updating an existing waiting list. All fields are optional."""

    name: Optional[str] = None
    """Updated name."""

    description: Optional[str] = None
    """Updated description."""


class WaitingListInDB(WaitingListBase):
    """Schema representing a waiting list as stored in the database. Includes database-specific fields."""

    id: UUID
    """Unique identifier for the waiting list in the database."""

    created_at: datetime
    """Timestamp when the waiting list record was created."""

    updated_at: datetime
    """Timestamp when the waiting list record was last updated."""

    model_config = {"from_attributes": True}


class WaitingList(WaitingListInDB):
    """Schema for waiting list data returned in API responses. Inherits all fields from WaitingListInDB."""

    pass


# Member-related schemas


class WaitingListMemberBase(BaseModel):
    """Base waiting list member model."""

    contact_id: UUID
    """ID of the contact on the waiting list."""

    status: str
    """Status of the member on the waiting list (e.g., 'pending', 'approved', 'rejected')."""


class WaitingListMemberCreate(WaitingListMemberBase):
    """Schema for adding a member to a waiting list."""

    pass


class WaitingListMemberUpdate(BaseModel):
    """Schema for updating a waiting list member."""

    status: Optional[str] = None
    """Updated status."""


class WaitingListMember(BaseModel):
    """Schema for waiting list member data."""

    id: UUID
    """Unique identifier for the member record."""

    waiting_list_id: UUID
    """ID of the waiting list."""

    contact_id: UUID
    """ID of the contact."""

    contact: Contact
    """Contact information."""

    status: str
    """Current status of the member."""

    created_at: datetime
    """Timestamp when the member was added."""

    model_config = {"from_attributes": True}


class AddWaitingListMembersRequest(BaseModel):
    """Schema for adding members to a waiting list."""

    contact_ids: list[UUID]
    """List of contact IDs to add to the waiting list."""

    status: str
    """Initial status for the members. Defaults to 'pending'."""

    def __init__(self, **data):
        # Set default status if not provided
        if "status" not in data:
            from app.constants.waiting_list import WaitingListMemberStatus

            data["status"] = WaitingListMemberStatus.PENDING
        super().__init__(**data)


class WaitingListMemberCountResponse(BaseModel):
    """Schema for waiting list member count response."""

    waiting_list_id: UUID
    """ID of the waiting list."""

    count: int
    """Number of active members in the waiting list."""


class ListMembersResponse(BaseModel):
    """Schema for listing waiting list members."""

    waiting_list_id: UUID
    """ID of the waiting list."""

    members: list[WaitingListMember]
    """List of members in the waiting list."""

    model_config = {"from_attributes": True}

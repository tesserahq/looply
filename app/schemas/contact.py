from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID
from datetime import datetime


class ContactBase(BaseModel):
    """Base contact model containing common contact attributes."""

    id: Optional[UUID] = None
    """Unique identifier for the contact. Defaults to None."""

    first_name: Optional[str] = None
    """Contact's first name. Optional field."""

    middle_name: Optional[str] = None
    """Contact's middle name. Optional field."""

    last_name: Optional[str] = None
    """Contact's last name. Optional field."""

    company: Optional[str] = None
    """Contact's company name. Optional field."""

    job: Optional[str] = None
    """Contact's job title. Optional field."""

    contact_type: str
    """Type of contact (e.g., 'personal', 'business'). Required field."""

    phone_type: str
    """Type of phone number (e.g., 'mobile', 'work', 'home'). Required field."""

    phone: Optional[str] = None
    """Contact's phone number. Optional field."""

    email: Optional[EmailStr] = None
    """Contact's email address. Must be a valid email format if provided."""

    website: Optional[str] = None
    """Contact's website URL. Optional field."""

    address_line_1: Optional[str] = None
    """First line of contact's address. Optional field."""

    address_line_2: Optional[str] = None
    """Second line of contact's address. Optional field."""

    city: Optional[str] = None
    """Contact's city. Optional field."""

    state: Optional[str] = None
    """Contact's state or province. Optional field."""

    zip_code: Optional[str] = None
    """Contact's postal or ZIP code. Optional field."""

    country: Optional[str] = None
    """Contact's country. Optional field."""

    notes: Optional[str] = None
    """Additional notes about the contact. Optional field."""

    is_active: bool = True
    """Whether the contact is active. Defaults to True."""

    created_by_id: UUID
    """ID of the user who created this contact. Required field."""


class ContactCreate(ContactBase):
    """Schema for creating a new contact. Inherits all fields from ContactBase."""

    pass


class ContactCreateRequest(BaseModel):
    """Schema for creating a new contact. Inherits all fields from ContactBase."""

    first_name: Optional[str] = None
    """Contact's first name. Optional field."""

    middle_name: Optional[str] = None
    """Contact's middle name. Optional field."""

    last_name: Optional[str] = None
    """Contact's last name. Optional field."""

    company: Optional[str] = None
    """Contact's company name. Optional field."""

    job: Optional[str] = None
    """Contact's job title. Optional field."""

    contact_type: str
    """Type of contact (e.g., 'personal', 'business'). Required field."""

    phone_type: str
    """Type of phone number (e.g., 'mobile', 'work', 'home'). Required field."""

    phone: Optional[str] = None
    """Contact's phone number. Optional field."""

    email: Optional[EmailStr] = None
    """Contact's email address. Must be a valid email format if provided."""

    website: Optional[str] = None
    """Contact's website URL. Optional field."""

    address_line_1: Optional[str] = None
    """First line of contact's address. Optional field."""

    address_line_2: Optional[str] = None
    """Second line of contact's address. Optional field."""

    city: Optional[str] = None
    """Contact's city. Optional field."""

    state: Optional[str] = None
    """Contact's state or province. Optional field."""

    zip_code: Optional[str] = None
    """Contact's postal or ZIP code. Optional field."""

    country: Optional[str] = None
    """Contact's country. Optional field."""

    notes: Optional[str] = None
    """Additional notes about the contact. Optional field."""

    is_active: bool = True
    """Whether the contact is active. Defaults to True."""


class ContactUpdate(BaseModel):
    """Schema for updating an existing contact. All fields are optional."""

    first_name: Optional[str] = None
    """Updated first name."""

    middle_name: Optional[str] = None
    """Updated middle name."""

    last_name: Optional[str] = None
    """Updated last name."""

    company: Optional[str] = None
    """Updated company name."""

    job: Optional[str] = None
    """Updated job title."""

    contact_type: Optional[str] = None
    """Updated contact type."""

    phone_type: Optional[str] = None
    """Updated phone type."""

    phone: Optional[str] = None
    """Updated phone number."""

    email: Optional[EmailStr] = None
    """Updated email address."""

    website: Optional[str] = None
    """Updated website URL."""

    address_line_1: Optional[str] = None
    """Updated first address line."""

    address_line_2: Optional[str] = None
    """Updated second address line."""

    city: Optional[str] = None
    """Updated city."""

    state: Optional[str] = None
    """Updated state or province."""

    zip_code: Optional[str] = None
    """Updated postal or ZIP code."""

    country: Optional[str] = None
    """Updated country."""

    notes: Optional[str] = None
    """Updated notes."""

    is_active: Optional[bool] = None
    """Updated active status."""


class ContactInDB(ContactBase):
    """Schema representing a contact as stored in the database. Includes database-specific fields."""

    id: UUID
    """Unique identifier for the contact in the database."""

    created_at: datetime
    """Timestamp when the contact record was created."""

    updated_at: datetime
    """Timestamp when the contact record was last updated."""

    model_config = {"from_attributes": True}


class Contact(ContactInDB):
    """Schema for contact data returned in API responses. Inherits all fields from ContactInDB."""

    pass


class ContactDetails(BaseModel):
    """Schema for detailed contact information, typically used in contact views."""

    id: UUID
    """Unique identifier for the contact."""

    first_name: Optional[str] = None
    """Contact's first name."""

    middle_name: Optional[str] = None
    """Contact's middle name."""

    last_name: Optional[str] = None
    """Contact's last name."""

    company: Optional[str] = None
    """Contact's company name."""

    job: Optional[str] = None
    """Contact's job title."""

    contact_type: str
    """Type of contact."""

    phone_type: str
    """Type of phone number."""

    phone: Optional[str] = None
    """Contact's phone number."""

    email: Optional[EmailStr] = None
    """Contact's email address."""

    website: Optional[str] = None
    """Contact's website URL."""

    address_line_1: Optional[str] = None
    """First line of contact's address."""

    address_line_2: Optional[str] = None
    """Second line of contact's address."""

    city: Optional[str] = None
    """Contact's city."""

    state: Optional[str] = None
    """Contact's state or province."""

    zip_code: Optional[str] = None
    """Contact's postal or ZIP code."""

    country: Optional[str] = None
    """Contact's country."""

    notes: Optional[str] = None
    """Additional notes about the contact."""

    is_active: bool
    """Whether the contact is active."""

    created_by_id: UUID
    """ID of the user who created this contact."""

    created_at: datetime
    """Timestamp when the contact record was created."""

    updated_at: datetime
    """Timestamp when the contact record was last updated."""

    model_config = {"from_attributes": True}

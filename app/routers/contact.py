from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate

from app.db import get_db
from app.schemas.contact import (
    Contact,
    ContactCreate,
    ContactCreateRequest,
    ContactUpdate,
)
from app.services.contact_service import ContactService
from app.schemas.user import User
from tessera_sdk.utils.auth import get_current_user

router = APIRouter(
    prefix="/contacts",
    tags=["contacts"],
    responses={404: {"description": "Not found"}},
)


@router.post("", response_model=Contact, status_code=status.HTTP_201_CREATED)
def create_contact(
    contact_data: ContactCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new contact."""
    contact_service = ContactService(db)

    # Check if email already exists
    if contact_data.email and contact_service.get_contact_by_email(contact_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Check if phone already exists
    if contact_data.phone and contact_service.get_contact_by_phone(contact_data.phone):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number already registered",
        )
    contact = ContactCreate(
        **contact_data.model_dump(),
        created_by_id=current_user.id,
    )

    return contact_service.create_contact(contact)


@router.get("", response_model=Page[Contact])
def list_contacts(db: Session = Depends(get_db)):
    """List all contacts with pagination."""
    contact_service = ContactService(db)
    return paginate(db, contact_service.get_contacts_query())


@router.get("/search", response_model=Page[Contact])
def search_contacts(
    q: str,
    db: Session = Depends(get_db),
):
    """
    Search contacts by text using PostgreSQL full-text search.

    Args:
        q: The search query term

    Returns:
        Page[Contact]: Paginated list of contacts matching the search term
    """
    if not q:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query parameter 'q' is required",
        )

    contact_service = ContactService(db)
    return paginate(db, contact_service.get_search_text_query(q))


@router.get("/{contact_id}", response_model=Contact)
def get_contact(contact_id: UUID, db: Session = Depends(get_db)):
    """Get a contact by ID."""
    contact = ContactService(db).get_contact(contact_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )
    return contact


@router.put("/{contact_id}", response_model=Contact)
def update_contact(
    contact_id: UUID, contact: ContactUpdate, db: Session = Depends(get_db)
):
    """Update a contact."""
    contact_service = ContactService(db)

    # Check if email is being updated and already exists
    if contact.email:
        existing_contact = contact_service.get_contact_by_email(contact.email)
        if existing_contact and existing_contact.id != contact_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

    # Check if phone is being updated and already exists
    if contact.phone:
        existing_contact = contact_service.get_contact_by_phone(contact.phone)
        if existing_contact and existing_contact.id != contact_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already registered",
            )

    updated_contact = contact_service.update_contact(contact_id, contact)
    if not updated_contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )
    return updated_contact


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(contact_id: UUID, db: Session = Depends(get_db)):
    """Delete a contact."""
    if not ContactService(db).delete_contact(contact_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )

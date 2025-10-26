from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from typing import Dict, Any

from app.db import get_db
from app.schemas.contact_list import (
    ContactList,
    ContactListCreate,
    ContactListCreateRequest,
    ContactListUpdate,
)
from app.services.contact_list_service import ContactListService
from app.models.contact_list import ContactList as ContactListModel
from app.schemas.user import User
from tessera_sdk.utils.auth import get_current_user

router = APIRouter(
    prefix="/contact-lists",
    tags=["contact-lists"],
    responses={404: {"description": "Not found"}},
)


@router.post("", response_model=ContactList, status_code=status.HTTP_201_CREATED)
def create_contact_list(
    contact_list_data: ContactListCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new contact list."""
    contact_list = ContactListCreate(
        **contact_list_data.model_dump(),
        created_by_id=current_user.id,
    )

    contact_list_service = ContactListService(db)
    return contact_list_service.create_contact_list(contact_list)


@router.get("", response_model=Page[ContactList])
def list_contact_lists(db: Session = Depends(get_db)):
    """List all contact lists with pagination."""
    contact_list_service = ContactListService(db)
    return paginate(db, contact_list_service.get_contact_lists_query())


@router.get("/{contact_list_id}", response_model=ContactList)
def get_contact_list(contact_list_id: UUID, db: Session = Depends(get_db)):
    """Get a contact list by ID."""
    contact_list = ContactListService(db).get_contact_list(contact_list_id)
    if not contact_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact list not found"
        )
    return contact_list


@router.put("/{contact_list_id}", response_model=ContactList)
def update_contact_list(
    contact_list_id: UUID,
    contact_list: ContactListUpdate,
    db: Session = Depends(get_db),
):
    """Update a contact list."""
    updated_contact_list = ContactListService(db).update_contact_list(
        contact_list_id, contact_list
    )
    if not updated_contact_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact list not found"
        )
    return updated_contact_list


@router.delete("/{contact_list_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact_list(contact_list_id: UUID, db: Session = Depends(get_db)):
    """Delete a contact list."""
    if not ContactListService(db).delete_contact_list(contact_list_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact list not found"
        )


@router.post("/search", response_model=list[ContactList])
def search_contact_lists(
    filters: Dict[str, Any],
    db: Session = Depends(get_db),
):
    """Search contact lists based on dynamic filter criteria."""
    contact_list_service = ContactListService(db)
    results = contact_list_service.search(filters)
    return results

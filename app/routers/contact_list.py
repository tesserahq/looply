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
    AddMembersRequest,
    MemberCountResponse,
    ListMembersResponse,
)
from app.services.contact_list_service import ContactListService
from app.schemas.contact import Contact
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


# Member management endpoints


@router.post("/{contact_list_id}/members")
def add_members_to_list(
    contact_list_id: UUID,
    request: AddMembersRequest,
    db: Session = Depends(get_db),
):
    """Add contacts to a contact list."""
    contact_list_service = ContactListService(db)

    # Check if contact list exists
    contact_list = contact_list_service.get_contact_list(contact_list_id)
    if not contact_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact list not found"
        )

    # Add contacts
    added_count = contact_list_service.add_contacts_to_list(
        contact_list_id, request.contact_ids
    )

    return {
        "message": f"Successfully added {added_count} contact(s) to the list",
        "added_count": added_count,
        "requested_count": len(request.contact_ids),
    }


@router.delete(
    "/{contact_list_id}/members/{contact_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_member_from_list(
    contact_list_id: UUID,
    contact_id: UUID,
    db: Session = Depends(get_db),
):
    """Remove a contact from a contact list."""
    contact_list_service = ContactListService(db)

    if not contact_list_service.remove_contact_from_list(contact_list_id, contact_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact list or contact not found, or contact is not in the list",
        )


@router.get("/{contact_list_id}/members", response_model=ListMembersResponse)
def get_list_members(contact_list_id: UUID, db: Session = Depends(get_db)):
    """Get all members of a contact list."""
    contact_list_service = ContactListService(db)

    # Check if contact list exists
    contact_list = contact_list_service.get_contact_list(contact_list_id)
    if not contact_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact list not found"
        )

    members = contact_list_service.get_list_members(contact_list_id)

    return ListMembersResponse(contact_list_id=contact_list_id, members=members)


@router.get("/{contact_list_id}/members/count", response_model=MemberCountResponse)
def get_list_member_count(contact_list_id: UUID, db: Session = Depends(get_db)):
    """Get the number of members in a contact list."""
    contact_list_service = ContactListService(db)

    # Check if contact list exists
    contact_list = contact_list_service.get_contact_list(contact_list_id)
    if not contact_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact list not found"
        )

    count = contact_list_service.get_list_member_count(contact_list_id)

    return MemberCountResponse(contact_list_id=contact_list_id, count=count)


@router.delete("/{contact_list_id}/members", status_code=status.HTTP_200_OK)
def clear_list_members(contact_list_id: UUID, db: Session = Depends(get_db)):
    """Clear all members from a contact list."""
    contact_list_service = ContactListService(db)

    # Check if contact list exists
    contact_list = contact_list_service.get_contact_list(contact_list_id)
    if not contact_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact list not found"
        )

    removed_count = contact_list_service.clear_list_members(contact_list_id)

    return {
        "message": f"Successfully removed {removed_count} contact(s) from the list",
        "removed_count": removed_count,
    }


@router.get("/contacts/{contact_id}/contact-lists", response_model=list[ContactList])
def get_contact_lists_for_contact(contact_id: UUID, db: Session = Depends(get_db)):
    """Get all contact lists that a contact belongs to."""
    from app.services.contact_service import ContactService

    # Check if contact exists
    contact = ContactService(db).get_contact(contact_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )

    contact_list_service = ContactListService(db)
    contact_lists = contact_list_service.get_contact_lists_for_contact(contact_id)

    return contact_lists


@router.get("/{contact_list_id}/members/{contact_id}/is-member")
def check_contact_membership(
    contact_list_id: UUID,
    contact_id: UUID,
    db: Session = Depends(get_db),
):
    """Check if a contact is a member of a contact list."""
    contact_list_service = ContactListService(db)

    # Check if contact list exists
    contact_list = contact_list_service.get_contact_list(contact_list_id)
    if not contact_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact list not found"
        )

    is_member = contact_list_service.is_contact_in_list(contact_list_id, contact_id)

    return {
        "contact_list_id": contact_list_id,
        "contact_id": contact_id,
        "is_member": is_member,
    }

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
from fastapi_pagination import Page
from fastapi_pagination import paginate as paginate_sequence
from fastapi_pagination.ext.sqlalchemy import paginate

from app.db import get_db
from app.schemas.contact import (
    Contact,
    ContactCreateRequest,
    ContactUpdate,
    ContactTypeOption,
    CONTACT_TYPE_OPTIONS,
)
from app.repositories.contact_repository import ContactRepository
from app.repositories.contact_list_repository import ContactListRepository
from app.schemas.contact_list import ContactWithLists
from app.schemas.user import User
from tessera_sdk.server.dependencies.auth import get_current_user
from app.auth.rbac import build_rbac_dependencies
from app.commands.contact.create_contact_command import CreateContactCommand
from app.commands.contact.update_contact_command import UpdateContactCommand
from app.commands.contact.delete_contact_command import DeleteContactCommand
from app.commands.contact.batch_create_contacts_command import (
    BatchCreateContactsCommand,
)

router = APIRouter(
    prefix="/contacts",
    tags=["contacts"],
    responses={404: {"description": "Not found"}},
)

RESOURCE = "contact"
rbac = build_rbac_dependencies(resource=RESOURCE)


@router.post("", response_model=Contact, status_code=status.HTTP_201_CREATED)
def create_contact(
    contact_data: ContactCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _authorized: bool = Depends(rbac["create"]),
):
    """Create a new contact."""
    try:
        command = CreateContactCommand(db)
        contact = command.execute(contact_data, current_user.id)
        return contact
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create contact: {str(e)}",
        )


@router.post(
    "/batch", response_model=list[Contact], status_code=status.HTTP_201_CREATED
)
def batch_create_contacts(
    contacts_data: list[ContactCreateRequest],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _authorized: bool = Depends(rbac["create"]),
):
    """Batch create multiple contacts."""
    try:
        command = BatchCreateContactsCommand(db)
        contacts = command.execute(contacts_data, current_user.id)
        return contacts
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to batch create contacts: {str(e)}",
        )


@router.get("", response_model=Page[Contact])
def list_contacts(
    tags: Optional[str] = Query(
        None,
        description="Comma-separated tag names. Returns contacts having at "
        "least one of them (OR semantics).",
    ),
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["read"]),
):
    """List all contacts with pagination, optionally filtered by tag."""
    contact_repository = ContactRepository(db)
    if tags:
        tag_names = [t.strip() for t in tags.split(",") if t.strip()]
        return paginate(db, contact_repository.get_contacts_by_tags_query(tag_names))
    return paginate(db, contact_repository.get_contacts_query())


@router.get("/search", response_model=Page[Contact])
def search_contacts(
    q: str,
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["read"]),
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

    contact_repository = ContactRepository(db)
    return paginate(db, contact_repository.get_search_text_query(q))


@router.get("/contact-types", response_model=Page[ContactTypeOption])
def list_contact_types(
    _authorized: bool = Depends(rbac["read"]),
):
    """List the fixed set of contact types available to assign to a contact."""
    return paginate_sequence(CONTACT_TYPE_OPTIONS)


@router.get("/{contact_id}", response_model=ContactWithLists)
def get_contact(
    contact_id: UUID,
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["read"]),
):
    """Get a contact by ID, including the contact lists it belongs to."""
    contact = ContactRepository(db).get_contact(contact_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )
    contact_lists = ContactListRepository(db).get_contact_lists_for_contact(contact_id)
    return ContactWithLists(
        **Contact.model_validate(contact).model_dump(),
        contact_lists=contact_lists,  # type: ignore[arg-type]
    )


@router.put("/{contact_id}", response_model=Contact)
def update_contact(
    contact_id: UUID,
    contact: ContactUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _authorized: bool = Depends(rbac["update"]),
):
    """Update a contact."""
    try:
        command = UpdateContactCommand(db)
        updated_contact = command.execute(contact_id, contact, current_user)
        return updated_contact
    except ValueError as e:
        # Check if it's a "not found" error
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update contact: {str(e)}",
        )


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    contact_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _authorized: bool = Depends(rbac["delete"]),
):
    """Delete a contact."""
    try:
        command = DeleteContactCommand(db)
        deleted = command.execute(contact_id, current_user)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
            )
    except ValueError as e:
        # Check if it's a "not found" error
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete contact: {str(e)}",
        )

from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional
from uuid import UUID
from fastapi_pagination import Page
from fastapi_pagination import paginate as paginate_sequence
from fastapi_pagination.ext.sqlalchemy import paginate

from app.db import DbSession
from app.schemas.contact import (
    Contact,
    ContactCreateRequest,
    ContactUpdate,
    ContactType,
    ContactTypeOption,
    CONTACT_TYPE_OPTIONS,
    ContactStatus,
    ContactStatusOption,
    CONTACT_STATUS_OPTIONS,
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
    db: DbSession,
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
    db: DbSession,
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
    db: DbSession,
    q: Optional[str] = Query(
        None, description="Free-text search term (PostgreSQL full-text search)."
    ),
    status_filter: Optional[ContactStatus] = Query(
        None, alias="status", description="Exact contact status to filter by."
    ),
    contact_type_filter: Optional[ContactType] = Query(
        None,
        alias="contact_type",
        description="Exact contact type to filter by.",
    ),
    tags: Optional[str] = Query(
        None,
        description="Comma-separated tag names. Returns contacts having at "
        "least one of them (OR semantics).",
    ),
    _authorized: bool = Depends(rbac["read"]),
):
    """List contacts with pagination, optionally narrowed by any combination
    of full-text search (q), status, contact_type, and tags (all filters are
    ANDed together)."""
    contact_repository = ContactRepository(db)
    tag_names = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    query = contact_repository.list_contacts_query(
        q=q,
        status=status_filter.value if status_filter else None,
        contact_type=contact_type_filter.value if contact_type_filter else None,
        tag_names=tag_names,
    )
    return paginate(db, query)


@router.get("/contact-types", response_model=Page[ContactTypeOption])
def list_contact_types(
    _authorized: bool = Depends(rbac["read"]),
):
    """List the fixed set of contact types available to assign to a contact."""
    return paginate_sequence(CONTACT_TYPE_OPTIONS)


@router.get("/contact-statuses", response_model=Page[ContactStatusOption])
def list_contact_statuses(
    _authorized: bool = Depends(rbac["read"]),
):
    """List the fixed set of lifecycle statuses (active/inactive/pending)
    available to assign to a contact. See
    docs/prds/0005-contact-status-and-event-mapping-defaults.md."""
    return paginate_sequence(CONTACT_STATUS_OPTIONS)


@router.get("/{contact_id}", response_model=ContactWithLists)
def get_contact(
    contact_id: UUID,
    db: DbSession,
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
    db: DbSession,
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
    db: DbSession,
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

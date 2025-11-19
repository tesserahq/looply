from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from app.db import get_db
from app.services.contact_service import ContactService
from app.models.contact import Contact


def get_contact_by_id(contact_id: UUID, db: Session = Depends(get_db)) -> Contact:
    """
    Dependency to get a contact by ID.
    Raises 404 if contact is not found.

    Args:
        contact_id: The ID of the contact to retrieve
        db: Database session

    Returns:
        Contact: The contact instance

    Raises:
        HTTPException: 404 if contact not found
    """
    contact_service = ContactService(db)
    contact = contact_service.get_contact(contact_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )
    return contact

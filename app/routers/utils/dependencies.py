from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from app.db import get_db
from app.repositories.contact_repository import ContactRepository
from app.repositories.campaign_repository import CampaignRepository
from app.models.contact import Contact
from app.models.campaign import Campaign


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
    contact_repository = ContactRepository(db)
    contact = contact_repository.get_contact(contact_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )
    return contact


def get_campaign_by_id(campaign_id: UUID, db: Session = Depends(get_db)) -> Campaign:
    """
    Dependency to get a campaign by ID.
    Raises 404 if campaign is not found.

    Args:
        campaign_id: The ID of the campaign to retrieve
        db: Database session

    Returns:
        Campaign: The campaign instance

    Raises:
        HTTPException: 404 if campaign not found
    """
    campaign_repository = CampaignRepository(db)
    campaign = campaign_repository.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found"
        )
    return campaign

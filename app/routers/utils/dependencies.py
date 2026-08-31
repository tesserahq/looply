from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from app.db import get_db
from app.repositories.contact_repository import ContactRepository
from app.repositories.campaign_repository import CampaignRepository
from app.repositories.segment_repository import SegmentRepository
from app.repositories.custom_field_definition_repository import (
    CustomFieldDefinitionRepository,
)
from app.repositories.event_field_mapping_repository import (
    EventFieldMappingRepository,
)
from app.repositories.tracked_event_type_repository import (
    TrackedEventTypeRepository,
)
from app.repositories.custom_event_repository import CustomEventRepository
from app.models.contact import Contact
from app.models.campaign import Campaign
from app.models.segment import Segment
from app.models.custom_field_definition import CustomFieldDefinition
from app.models.event_field_mapping import EventFieldMapping
from app.models.tracked_event_type import TrackedEventType
from app.models.custom_event import CustomEvent


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


def get_contact_by_external_id(
    external_id: str, db: Session = Depends(get_db)
) -> Contact:
    """
    Dependency to get a contact by its external host platform identity.
    Raises 404 if no contact with that external_id exists - field writes don't carry
    enough contact info (no email/name) to safely auto-create one, unlike event
    ingestion (see docs/prds/0002-contact-custom-fields-and-events.md).

    Args:
        external_id: The external id of the contact to retrieve
        db: Database session

    Returns:
        Contact: The contact instance

    Raises:
        HTTPException: 404 if no contact with that external_id exists
    """
    contact_repository = ContactRepository(db)
    contact = contact_repository.get_contact_by_external_id(external_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No contact with external_id {external_id!r} exists",
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


def get_segment_by_id(segment_id: UUID, db: Session = Depends(get_db)) -> Segment:
    """
    Dependency to get a segment by ID.
    Raises 404 if segment is not found.

    Args:
        segment_id: The ID of the segment to retrieve
        db: Database session

    Returns:
        Segment: The segment instance

    Raises:
        HTTPException: 404 if segment not found
    """
    segment_repository = SegmentRepository(db)
    segment = segment_repository.get_segment(segment_id)
    if not segment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found"
        )
    return segment


def get_custom_field_definition_by_id(
    definition_id: UUID, db: Session = Depends(get_db)
) -> CustomFieldDefinition:
    """
    Dependency to get a custom field definition by ID.
    Raises 404 if not found (or soft-deleted).

    Args:
        definition_id: The ID of the definition to retrieve
        db: Database session

    Returns:
        CustomFieldDefinition: The definition instance

    Raises:
        HTTPException: 404 if not found
    """
    definition = CustomFieldDefinitionRepository(db).get_definition(definition_id)
    if not definition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom field definition not found",
        )
    return definition


def get_event_field_mapping_by_id(
    mapping_id: UUID, db: Session = Depends(get_db)
) -> EventFieldMapping:
    """
    Dependency to get an event-to-field mapping by ID.
    Raises 404 if not found (or soft-deleted).

    Args:
        mapping_id: The ID of the mapping to retrieve
        db: Database session

    Returns:
        EventFieldMapping: The mapping instance

    Raises:
        HTTPException: 404 if not found
    """
    mapping = EventFieldMappingRepository(db).get_mapping(mapping_id)
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event field mapping not found",
        )
    return mapping


def get_tracked_event_type_by_id(
    tracked_event_type_id: UUID, db: Session = Depends(get_db)
) -> TrackedEventType:
    """
    Dependency to get a tracked event type by ID.
    Raises 404 if not found (or soft-deleted).

    Args:
        tracked_event_type_id: The ID of the registration to retrieve
        db: Database session

    Returns:
        TrackedEventType: The registration instance

    Raises:
        HTTPException: 404 if not found
    """
    tracked = TrackedEventTypeRepository(db).get_tracked_event_type(
        tracked_event_type_id
    )
    if not tracked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tracked event type not found",
        )
    return tracked


def get_custom_event_by_id(
    event_id: UUID, db: Session = Depends(get_db)
) -> CustomEvent:
    """
    Dependency to get a custom event by ID.
    Raises 404 if not found.

    Args:
        event_id: The ID of the event to retrieve
        db: Database session

    Returns:
        CustomEvent: The event instance

    Raises:
        HTTPException: 404 if not found
    """
    event = CustomEventRepository(db).get_event(event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Custom event not found"
        )
    return event

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.schemas.stats import Stats, ContactInteractionWithContact, ContactSummary
from app.schemas.common import DataResponse
from app.services.stats_service import StatsService

router = APIRouter(
    prefix="/stats",
    tags=["stats"],
    responses={404: {"description": "Not found"}},
)


@router.get("", response_model=DataResponse[Stats])
def get_stats(db: Session = Depends(get_db)):
    """Get statistics about contacts, lists, and upcoming interactions."""
    stats_service = StatsService(db)

    number_of_contacts = stats_service.get_number_of_contacts()
    number_of_lists = stats_service.get_number_of_lists()
    number_of_public_lists = stats_service.get_number_of_public_lists()
    number_of_private_lists = stats_service.get_number_of_private_lists()
    interactions_with_contacts = stats_service.get_upcoming_interactions()
    recent_contacts = stats_service.get_last_contacts(limit=5)

    # Construct ContactInteractionWithContact objects with nested contact
    upcoming_interactions = []
    for interaction, contact in interactions_with_contacts:
        contact_summary = ContactSummary.model_validate(contact)
        # Create interaction data from the model, then add contact
        # First get the base interaction data
        from app.schemas.contact_interaction import ContactInteractionInDB

        base_interaction = ContactInteractionInDB.model_validate(
            interaction, from_attributes=True
        )
        # Now create the full interaction with contact
        interaction_data = ContactInteractionWithContact(
            **base_interaction.model_dump(),
            contact=contact_summary,
        )
        upcoming_interactions.append(interaction_data)

    # Convert recent contacts to ContactSummary
    recent_contacts_summary = [
        ContactSummary.model_validate(contact) for contact in recent_contacts
    ]

    stats = Stats(
        total_contacts=number_of_contacts,
        total_list=number_of_lists,
        total_public_list=number_of_public_lists,
        total_private_list=number_of_private_lists,
        upcoming_interactions=upcoming_interactions,
        recent_contacts=recent_contacts_summary,
    )

    return DataResponse(data=stats)

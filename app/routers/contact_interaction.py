from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime, timezone
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate

from app.db import get_db
from app.schemas.contact_interaction import (
    ContactInteraction,
    ContactInteractionCreate,
    ContactInteractionCreateRequest,
    ContactInteractionUpdate,
)
from app.services.contact_interaction_service import ContactInteractionService
from app.schemas.user import User
from app.routers.utils.dependencies import get_contact_by_id
from app.models.contact import Contact
from app.constants.contact_interaction import ContactInteractionAction
from tessera_sdk.utils.auth import get_current_user

router = APIRouter(
    prefix="/contact-interactions",
    tags=["contact-interactions"],
    responses={404: {"description": "Not found"}},
)

# Nested router for contact-specific interactions
nested_router = APIRouter(
    prefix="/contacts/{contact_id}/interactions",
    tags=["contact-interactions"],
    responses={404: {"description": "Not found"}},
)


@router.get("/actions")
def list_actions():
    """Get all available actions for contact interactions."""
    actions = ContactInteractionAction.get_all_with_labels()

    return {
        "items": actions,
        "size": len(actions),
        "page": 1,
        "pages": 1,
        "total": len(actions),
    }


@router.get("/pending-actions", response_model=Page[ContactInteraction])
def get_pending_actions(db: Session = Depends(get_db)):
    """Get all pending actions across all contacts."""
    interaction_service = ContactInteractionService(db)
    return paginate(db, interaction_service.get_pending_actions_query())


@nested_router.post(
    "", response_model=ContactInteraction, status_code=status.HTTP_201_CREATED
)
def create_contact_interaction(
    interaction_data: ContactInteractionCreateRequest,
    contact: Contact = Depends(get_contact_by_id),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new interaction for a contact."""
    interaction_service = ContactInteractionService(db)

    # Set interaction_timestamp to current time if not provided
    interaction_timestamp = (
        interaction_data.interaction_timestamp
        if interaction_data.interaction_timestamp
        else datetime.now(timezone.utc)
    )

    interaction = ContactInteractionCreate(
        **interaction_data.model_dump(exclude={"interaction_timestamp"}),
        contact_id=contact.id,
        interaction_timestamp=interaction_timestamp,
        created_by_id=current_user.id,
    )

    return interaction_service.create_contact_interaction(interaction)


@nested_router.get("", response_model=Page[ContactInteraction])
def list_contact_interactions(
    contact: Contact = Depends(get_contact_by_id),
    db: Session = Depends(get_db),
):
    """List all interactions for a specific contact with pagination."""
    interaction_service = ContactInteractionService(db)
    return paginate(
        db, interaction_service.get_interactions_by_contact_query(contact.id)
    )


@nested_router.get("/last", response_model=ContactInteraction)
def get_last_contact_interaction(
    contact: Contact = Depends(get_contact_by_id),
    db: Session = Depends(get_db),
):
    """Get the most recent interaction for a contact."""
    interaction_service = ContactInteractionService(db)
    last_interaction = interaction_service.get_last_interaction(contact.id)
    if not last_interaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No interactions found for this contact",
        )
    return last_interaction


# Global item routes
@router.get("/{interaction_id}", response_model=ContactInteraction)
def get_contact_interaction(interaction_id: UUID, db: Session = Depends(get_db)):
    """Get a contact interaction by ID."""
    interaction = ContactInteractionService(db).get_contact_interaction(interaction_id)
    if not interaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact interaction not found",
        )
    return interaction


@router.put("/{interaction_id}", response_model=ContactInteraction)
def update_contact_interaction(
    interaction_id: UUID,
    interaction: ContactInteractionUpdate,
    db: Session = Depends(get_db),
):
    """Update a contact interaction."""
    updated_interaction = ContactInteractionService(db).update_contact_interaction(
        interaction_id, interaction
    )
    if not updated_interaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact interaction not found",
        )
    return updated_interaction


@router.delete("/{interaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact_interaction(interaction_id: UUID, db: Session = Depends(get_db)):
    """Delete a contact interaction."""
    if not ContactInteractionService(db).delete_contact_interaction(interaction_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact interaction not found",
        )


@router.get("", response_model=Page[ContactInteraction])
def list_contact_interactions_global(db: Session = Depends(get_db)):
    """List all contact interactions with pagination."""
    interaction_service = ContactInteractionService(db)
    return paginate(db, interaction_service.get_contact_interactions_query())

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate

from app.db import get_db
from app.models.contact import Contact
from app.schemas.custom_event import CustomEvent
from app.repositories.custom_event_repository import CustomEventRepository
from app.routers.utils.dependencies import get_contact_by_external_id
from app.auth.rbac import build_rbac_dependencies

router = APIRouter(
    prefix="/custom-events",
    tags=["custom-events"],
    responses={404: {"description": "Not found"}},
)

# Nested under /contacts/{external_id} for the per-contact event history view
# (user story 11) - the top-level /custom-events router above is for the global
# firehose/discovery view (verifying ingestion is flowing at all, browsing which
# event_types have actually been seen) that isn't scoped to a known contact.
nested_router = APIRouter(
    prefix="/contacts/{external_id}/custom-events",
    tags=["custom-events"],
    responses={404: {"description": "Not found"}},
)

RESOURCE = "custom_event"
rbac = build_rbac_dependencies(resource=RESOURCE)


@router.get("", response_model=Page[CustomEvent])
def list_custom_events(
    name: Optional[str] = None,
    contact_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["read"]),
):
    """List all custom events, most recent first, with pagination - optionally
    filtered by event name and/or contact_id. Global (not contact-scoped) view for
    verifying NATS ingestion is flowing and browsing which event_types have
    actually been seen."""
    return paginate(
        db, CustomEventRepository(db).get_events_query(name=name, contact_id=contact_id)
    )


@nested_router.get("", response_model=list[CustomEvent])
def list_contact_custom_events(
    name: Optional[str] = None,
    contact: Contact = Depends(get_contact_by_external_id),
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["read"]),
):
    """List a contact's event history, most recent first, optionally filtered by
    event name (user story 11)."""
    return CustomEventRepository(db).list_events_for_contact(contact.id, name=name)

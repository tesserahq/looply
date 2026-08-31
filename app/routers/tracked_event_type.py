from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate

from app.db import get_db
from app.models.tracked_event_type import TrackedEventType as TrackedEventTypeModel
from app.schemas.tracked_event_type import (
    TrackedEventType,
    TrackedEventTypeCreate,
    TrackedEventTypeCreateRequest,
)
from app.repositories.tracked_event_type_repository import (
    TrackedEventTypeConflictError,
    TrackedEventTypeRepository,
)
from app.routers.utils.dependencies import get_tracked_event_type_by_id
from app.schemas.user import User
from tessera_sdk.server.dependencies.auth import get_current_user
from app.auth.rbac import build_rbac_dependencies

router = APIRouter(
    prefix="/tracked-event-types",
    tags=["tracked-event-types"],
    responses={404: {"description": "Not found"}},
)

RESOURCE = "tracked_event_type"
rbac = build_rbac_dependencies(resource=RESOURCE)


@router.post("", response_model=TrackedEventType, status_code=status.HTTP_201_CREATED)
def create_tracked_event_type(
    tracked_data: TrackedEventTypeCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _authorized: bool = Depends(rbac["create"]),
):
    """Register a new event_type to track - only tracked event types are ever
    turned into a CustomEvent row or evaluated against EventFieldMapping when
    ingested over NATS. See
    docs/prds/0002-contact-custom-fields-and-events.md, "Custom Events"."""
    tracked = TrackedEventTypeCreate(
        **tracked_data.model_dump(),
        created_by_id=current_user.id,
    )
    try:
        return TrackedEventTypeRepository(db).create_tracked_event_type(tracked)
    except TrackedEventTypeConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("", response_model=Page[TrackedEventType])
def list_tracked_event_types(
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["read"]),
):
    """List all actively tracked event types with pagination."""
    return paginate(db, TrackedEventTypeRepository(db).get_tracked_event_types_query())


@router.get("/{tracked_event_type_id}", response_model=TrackedEventType)
def get_tracked_event_type(
    tracked: TrackedEventTypeModel = Depends(get_tracked_event_type_by_id),
    _authorized: bool = Depends(rbac["read"]),
):
    """Get a tracked event type by ID."""
    return tracked


@router.delete("/{tracked_event_type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tracked_event_type(
    tracked_event_type_id: UUID,
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["delete"]),
):
    """Soft delete a tracked event type. Newly ingested events of this type stop
    being processed without a separate cleanup step."""
    if not TrackedEventTypeRepository(db).delete_tracked_event_type(
        tracked_event_type_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tracked event type not found",
        )

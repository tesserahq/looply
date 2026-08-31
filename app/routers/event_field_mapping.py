from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate

from app.db import get_db
from app.models.event_field_mapping import EventFieldMapping as EventFieldMappingModel
from app.schemas.event_field_mapping import (
    EventFieldMapping,
    EventFieldMappingCreate,
    EventFieldMappingCreateRequest,
    EventFieldMappingTargetType,
)
from app.repositories.event_field_mapping_repository import (
    DuplicateIdentityKeyError,
    EventFieldMappingRepository,
    InvalidEventFieldMappingError,
)
from app.repositories.custom_field_definition_repository import (
    CustomFieldDefinitionRepository,
)
from app.routers.utils.dependencies import get_event_field_mapping_by_id
from app.schemas.user import User
from tessera_sdk.server.dependencies.auth import get_current_user
from app.auth.rbac import build_rbac_dependencies

router = APIRouter(
    prefix="/event-field-mappings",
    tags=["event-field-mappings"],
    responses={404: {"description": "Not found"}},
)

RESOURCE = "event_field_mapping"
rbac = build_rbac_dependencies(resource=RESOURCE)


@router.post("", response_model=EventFieldMapping, status_code=status.HTTP_201_CREATED)
def create_event_field_mapping(
    mapping_data: EventFieldMappingCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _authorized: bool = Depends(rbac["create"]),
):
    """Create a new event-to-field mapping - declares that an ingested event of
    event_type should have source_path extracted from its event_data and written
    onto either a built-in Contact field or a custom field. Immutable once set;
    delete and recreate to change it. See
    docs/prds/0003-event-driven-contact-resolution.md."""
    field_definition_id = None
    if mapping_data.target_type == EventFieldMappingTargetType.CUSTOM_FIELD:
        definition = CustomFieldDefinitionRepository(db).get_definition_by_name(
            mapping_data.field_name
        )
        if not definition:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"No custom field definition named {mapping_data.field_name!r} exists",
            )
        field_definition_id = definition.id

    mapping = EventFieldMappingCreate(
        event_type=mapping_data.event_type,
        source_path=mapping_data.source_path,
        target_type=mapping_data.target_type,
        target_field=mapping_data.target_field,
        field_definition_id=field_definition_id,
        is_identity_key=mapping_data.is_identity_key,
        created_by_id=current_user.id,
    )
    try:
        return EventFieldMappingRepository(db).create_mapping(mapping)
    except InvalidEventFieldMappingError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)
        )
    except DuplicateIdentityKeyError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("", response_model=Page[EventFieldMapping])
def list_event_field_mappings(
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["read"]),
):
    """List all active event-to-field mappings with pagination."""
    return paginate(db, EventFieldMappingRepository(db).get_mappings_query())


@router.get("/{mapping_id}", response_model=EventFieldMapping)
def get_event_field_mapping(
    mapping: EventFieldMappingModel = Depends(get_event_field_mapping_by_id),
    _authorized: bool = Depends(rbac["read"]),
):
    """Get an event-to-field mapping by ID."""
    return mapping


@router.delete("/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event_field_mapping(
    mapping_id: UUID,
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["delete"]),
):
    """Soft delete a mapping. It stops being applied to newly ingested events
    without a separate cleanup step."""
    if not EventFieldMappingRepository(db).delete_mapping(mapping_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event field mapping not found",
        )

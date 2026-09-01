from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate

from app.db import get_db
from app.models.event_mapping import EventMapping as EventMappingModel
from app.models.event_field_mapping import EventFieldMapping as EventFieldMappingModel
from app.schemas.event_mapping import (
    EventMapping,
    EventMappingCreate,
    EventMappingCreateRequest,
    EventMappingUpdateRequest,
)
from app.schemas.event_field_mapping import (
    EventFieldMapping,
    EventFieldMappingCreate,
    EventFieldMappingCreateRequest,
    EventFieldMappingTargetType,
    EventFieldMappingUpdateRequest,
)
from app.repositories.event_mapping_repository import (
    EventMappingConflictError,
    EventMappingRepository,
    InvalidEventMappingError,
)
from app.repositories.event_field_mapping_repository import (
    EventFieldMappingRepository,
    InvalidEventFieldMappingError,
)
from app.repositories.custom_field_definition_repository import (
    CustomFieldDefinitionRepository,
)
from app.routers.utils.dependencies import (
    get_event_field_mapping_by_id,
    get_event_mapping_by_id,
)
from app.schemas.user import User
from tessera_sdk.server.dependencies.auth import get_current_user
from app.auth.rbac import build_rbac_dependencies

router = APIRouter(
    prefix="/event-mappings",
    tags=["event-mappings"],
    responses={404: {"description": "Not found"}},
)

# Nested under /event-mappings/{event_mapping_id} - attribute mappings only ever
# make sense scoped to their parent event, so the parent id is always in the URL
# rather than repeated in the payload (see docs/prds/0004-event-mapping-consolidation.md).
nested_router = APIRouter(
    prefix="/event-mappings/{event_mapping_id}/fields",
    tags=["event-mappings"],
    responses={404: {"description": "Not found"}},
)

RESOURCE = "event_mapping"
rbac = build_rbac_dependencies(resource=RESOURCE)


def _resolve_field_definition_id(db: Session, field_name: str) -> UUID:
    definition = CustomFieldDefinitionRepository(db).get_definition_by_name(field_name)
    if not definition:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"No custom field definition named {field_name!r} exists",
        )
    return definition.id


@router.post("", response_model=EventMapping, status_code=status.HTTP_201_CREATED)
def create_event_mapping(
    event_mapping_data: EventMappingCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _authorized: bool = Depends(rbac["create"]),
):
    """Register a new event_type to act on, optionally with its identity
    configuration (which payload path + Contact column identifies the contact).
    See docs/prds/0004-event-mapping-consolidation.md."""
    event_mapping = EventMappingCreate(
        **event_mapping_data.model_dump(),
        created_by_id=current_user.id,
    )
    try:
        return EventMappingRepository(db).create_event_mapping(event_mapping)
    except EventMappingConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except InvalidEventMappingError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)
        )


@router.get("", response_model=Page[EventMapping])
def list_event_mappings(
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["read"]),
):
    """List all active event mappings with pagination."""
    return paginate(db, EventMappingRepository(db).get_event_mappings_query())


@router.get("/{event_mapping_id}", response_model=EventMapping)
def get_event_mapping(
    event_mapping: EventMappingModel = Depends(get_event_mapping_by_id),
    _authorized: bool = Depends(rbac["read"]),
):
    """Get an event mapping by ID."""
    return event_mapping


@router.patch("/{event_mapping_id}", response_model=EventMapping)
def update_event_mapping(
    update_data: EventMappingUpdateRequest,
    event_mapping: EventMappingModel = Depends(get_event_mapping_by_id),
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["update"]),
):
    """Update an event mapping's source/identity configuration in place -
    editable, unlike its EventFieldMapping children before this PRD. See the
    model docstring for the accepted immutability trade-off."""
    try:
        return EventMappingRepository(db).update_event_mapping(
            event_mapping.id, update_data
        )
    except InvalidEventMappingError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)
        )


@router.delete("/{event_mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event_mapping(
    event_mapping_id: UUID,
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["delete"]),
):
    """Soft delete an event mapping, cascading to soft-delete all of its active
    field mappings. Newly ingested events of this type stop being processed
    without a separate cleanup step."""
    if not EventMappingRepository(db).delete_event_mapping(event_mapping_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event mapping not found",
        )


@nested_router.post("", response_model=EventFieldMapping, status_code=status.HTTP_201_CREATED)
def create_event_field_mapping(
    mapping_data: EventFieldMappingCreateRequest,
    event_mapping: EventMappingModel = Depends(get_event_mapping_by_id),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _authorized: bool = Depends(rbac["create"]),
):
    """Create a new attribute mapping under this event mapping - declares that
    source_path should be extracted from event_data and written onto either a
    built-in Contact field or a custom field, once this event's identity has
    resolved a contact. See docs/prds/0004-event-mapping-consolidation.md."""
    field_definition_id = None
    if mapping_data.target_type == EventFieldMappingTargetType.CUSTOM_FIELD:
        field_definition_id = _resolve_field_definition_id(db, mapping_data.field_name)

    mapping = EventFieldMappingCreate(
        event_mapping_id=event_mapping.id,
        source_path=mapping_data.source_path,
        target_type=mapping_data.target_type,
        target_field=mapping_data.target_field,
        field_definition_id=field_definition_id,
        created_by_id=current_user.id,
    )
    try:
        return EventFieldMappingRepository(db).create_mapping(mapping)
    except InvalidEventFieldMappingError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)
        )


@nested_router.get("", response_model=Page[EventFieldMapping])
def list_event_field_mappings(
    event_mapping: EventMappingModel = Depends(get_event_mapping_by_id),
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["read"]),
):
    """List all active attribute mappings for this event mapping, with pagination."""
    return paginate(
        db,
        EventFieldMappingRepository(db).get_mappings_query(
            event_mapping_id=event_mapping.id
        ),
    )


@nested_router.get("/{mapping_id}", response_model=EventFieldMapping)
def get_event_field_mapping(
    mapping: EventFieldMappingModel = Depends(get_event_field_mapping_by_id),
    _authorized: bool = Depends(rbac["read"]),
):
    """Get an attribute mapping by ID."""
    return mapping


@nested_router.patch("/{mapping_id}", response_model=EventFieldMapping)
def update_event_field_mapping(
    update_data: EventFieldMappingUpdateRequest,
    mapping: EventFieldMappingModel = Depends(get_event_field_mapping_by_id),
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["update"]),
):
    """Update an attribute mapping's source_path/target in place - editable,
    unlike before this PRD (see docs/prds/0004-event-mapping-consolidation.md)."""
    target_type = update_data.target_type or EventFieldMappingTargetType(
        mapping.target_type
    )

    field_definition_id = None
    target_field = None
    clear_field_definition_id = False
    clear_target_field = False

    if target_type == EventFieldMappingTargetType.CUSTOM_FIELD:
        clear_target_field = True
        if update_data.field_name is not None:
            field_definition_id = _resolve_field_definition_id(
                db, update_data.field_name
            )
        elif update_data.target_type is not None:
            # Switching an existing contact_field mapping to custom_field
            # without naming a field is meaningless - there's nothing to point
            # field_definition_id at.
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail='field_name is required when switching target_type to "custom_field"',
            )
    else:
        clear_field_definition_id = True
        target_field = update_data.target_field
        if target_field is None and update_data.target_type is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail='target_field is required when switching target_type to "contact_field"',
            )

    try:
        updated = EventFieldMappingRepository(db).update_mapping(
            mapping.id,
            source_path=update_data.source_path,
            target_type=update_data.target_type,
            target_field=target_field,
            field_definition_id=field_definition_id,
            clear_target_field=clear_target_field,
            clear_field_definition_id=clear_field_definition_id,
        )
    except InvalidEventFieldMappingError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)
        )
    return updated


@nested_router.delete("/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event_field_mapping(
    mapping: EventFieldMappingModel = Depends(get_event_field_mapping_by_id),
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["delete"]),
):
    """Soft delete an attribute mapping. It stops being applied to newly
    ingested events without a separate cleanup step."""
    EventFieldMappingRepository(db).delete_mapping(mapping.id)

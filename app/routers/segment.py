from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate

from app.db import get_db
from app.models.segment import Segment as SegmentModel
from app.schemas.contact import Contact
from app.schemas.segment import (
    Segment,
    SegmentCreate,
    SegmentCreateRequest,
    SegmentPreviewResponse,
    SegmentUpdate,
)
from app.schemas.segment_rule import SegmentRuleCreate
from app.repositories.segment_repository import (
    SegmentNameConflictError,
    SegmentRepository,
)
from app.repositories.segment_resolver import SegmentResolutionError, resolve_count
from app.routers.utils.dependencies import get_segment_by_id
from app.schemas.user import User
from tessera_sdk.server.dependencies.auth import get_current_user
from app.auth.rbac import build_rbac_dependencies

router = APIRouter(
    prefix="/segments",
    tags=["segments"],
    responses={404: {"description": "Not found"}},
)

RESOURCE = "segment"
rbac = build_rbac_dependencies(resource=RESOURCE)


@router.post("", response_model=Segment, status_code=status.HTTP_201_CREATED)
def create_segment(
    segment_data: SegmentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _authorized: bool = Depends(rbac["create"]),
):
    """Create a new segment."""
    segment = SegmentCreate(
        **segment_data.model_dump(),
        created_by_id=current_user.id,
    )
    try:
        return SegmentRepository(db).create_segment(segment)
    except SegmentResolutionError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)
        )
    except SegmentNameConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("", response_model=Page[Segment])
def list_segments(
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["read"]),
):
    """List all segments with pagination."""
    return paginate(db, SegmentRepository(db).get_segments_query())


@router.get("/{segment_id}", response_model=Segment)
def get_segment(
    segment: SegmentModel = Depends(get_segment_by_id),
    _authorized: bool = Depends(rbac["read"]),
):
    """Get a segment by ID."""
    return segment


@router.put("/{segment_id}", response_model=Segment)
def update_segment(
    segment_data: SegmentUpdate,
    existing_segment: SegmentModel = Depends(get_segment_by_id),
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["update"]),
):
    """Update a segment's name and/or rule."""
    try:
        return SegmentRepository(db).update_segment(existing_segment.id, segment_data)
    except SegmentResolutionError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)
        )
    except SegmentNameConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.delete("/{segment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_segment(
    existing_segment: SegmentModel = Depends(get_segment_by_id),
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["delete"]),
):
    """Delete a segment."""
    SegmentRepository(db).delete_segment(existing_segment.id)


@router.get("/{segment_id}/preview", response_model=SegmentPreviewResponse)
def preview_segment(
    segment: SegmentModel = Depends(get_segment_by_id),
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["read"]),
):
    """Live, non-persisted contact count for a saved segment."""
    try:
        count = SegmentRepository(db).preview_count(segment)
    except SegmentResolutionError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)
        )
    return SegmentPreviewResponse(contact_count=count)


@router.get("/{segment_id}/contacts", response_model=Page[Contact])
def list_segment_contacts(
    segment: SegmentModel = Depends(get_segment_by_id),
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["read"]),
):
    """Paginated list of contacts currently matching a saved segment."""
    try:
        return paginate(db, SegmentRepository(db).get_contacts_query(segment))
    except SegmentResolutionError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)
        )


@router.post("/preview", response_model=SegmentPreviewResponse)
def preview_draft_segment(
    rule: SegmentRuleCreate,
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["read"]),
):
    """Live, non-persisted contact count for a rule tree not yet saved as a segment."""
    try:
        count = resolve_count(db, rule.root)
    except SegmentResolutionError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)
        )
    return SegmentPreviewResponse(contact_count=count)

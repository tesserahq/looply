from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate

from app.db import get_db
from app.models.tag import Tag as TagModel
from app.schemas.tag import Tag, TagCreateRequest, TagUpdate, TagUsage, TagWithCounts
from app.repositories.tag_repository import TagConflictError, TagRepository
from app.repositories.segment_repository import SegmentRepository
from app.routers.utils.dependencies import get_tag_by_id
from app.schemas.user import User
from tessera_sdk.server.dependencies.auth import get_current_user
from app.auth.rbac import build_rbac_dependencies

router = APIRouter(
    prefix="/tags",
    tags=["tags"],
    responses={404: {"description": "Not found"}},
)

RESOURCE = "tag"
rbac = build_rbac_dependencies(resource=RESOURCE)


@router.post("", response_model=Tag, status_code=status.HTTP_201_CREATED)
def create_tag(
    tag_data: TagCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _authorized: bool = Depends(rbac["create"]),
):
    """Create a new tag."""
    try:
        return TagRepository(db).create_tag(tag_data.name, current_user.id)
    except TagConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("", response_model=Page[TagWithCounts])
def list_tags(
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["read"]),
):
    """List all active tags with pagination, including each tag's current
    contact/campaign assignment counts."""
    return paginate(
        db,
        TagRepository(db).get_tags_with_counts_query(),
        transformer=lambda rows: [
            TagWithCounts(
                **Tag.model_validate(tag).model_dump(),
                contacts_count=contacts_count,
                campaigns_count=campaigns_count,
            )
            for tag, contacts_count, campaigns_count in rows
        ],
    )


@router.get("/{tag_id}", response_model=Tag)
def get_tag(
    tag: TagModel = Depends(get_tag_by_id),
    _authorized: bool = Depends(rbac["read"]),
):
    """Get a tag by ID."""
    return tag


@router.get("/{tag_id}/usage", response_model=TagUsage)
def get_tag_usage(
    tag: TagModel = Depends(get_tag_by_id),
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["read"]),
):
    """A tag's full delete impact: assignment counts plus any saved segments
    that filter on it. Fetched by the delete-confirm dialog only, not part
    of the list, to avoid scanning every segment's rule on every page load.
    """
    contacts_count, campaigns_count = TagRepository(db).get_usage_counts(tag.id)
    segments = SegmentRepository(db).get_segments_referencing_tag(tag.id)
    return TagUsage(
        contacts_count=contacts_count,
        campaigns_count=campaigns_count,
        segments=segments,
    )


@router.put("/{tag_id}", response_model=Tag)
def update_tag(
    tag_data: TagUpdate,
    existing_tag: TagModel = Depends(get_tag_by_id),
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["update"]),
):
    """Rename a tag."""
    try:
        return TagRepository(db).update_tag(existing_tag.id, tag_data.name)
    except TagConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(
    existing_tag: TagModel = Depends(get_tag_by_id),
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["delete"]),
):
    """Delete a tag, removing it from every contact/campaign it's assigned to."""
    TagRepository(db).delete_tag(existing_tag.id)

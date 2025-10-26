from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from typing import Dict, Any

from app.db import get_db
from app.schemas.waiting_list import (
    WaitingList,
    WaitingListCreate,
    WaitingListCreateRequest,
    WaitingListUpdate,
    AddWaitingListMembersRequest,
    WaitingListMemberCountResponse,
)
from app.services.waiting_list_service import WaitingListService
from app.schemas.user import User
from tessera_sdk.utils.auth import get_current_user

router = APIRouter(
    prefix="/waiting-lists",
    tags=["waiting-lists"],
    responses={404: {"description": "Not found"}},
)


@router.post("", response_model=WaitingList, status_code=status.HTTP_201_CREATED)
def create_waiting_list(
    waiting_list_data: WaitingListCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new waiting list."""
    waiting_list = WaitingListCreate(
        **waiting_list_data.model_dump(),
        created_by_id=current_user.id,
    )

    waiting_list_service = WaitingListService(db)
    return waiting_list_service.create_waiting_list(waiting_list)


@router.get("", response_model=Page[WaitingList])
def list_waiting_lists(db: Session = Depends(get_db)):
    """List all waiting lists with pagination."""
    waiting_list_service = WaitingListService(db)
    return paginate(db, waiting_list_service.get_waiting_lists_query())


@router.get("/{waiting_list_id}", response_model=WaitingList)
def get_waiting_list(waiting_list_id: UUID, db: Session = Depends(get_db)):
    """Get a waiting list by ID."""
    waiting_list = WaitingListService(db).get_waiting_list(waiting_list_id)
    if not waiting_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Waiting list not found"
        )
    return waiting_list


@router.put("/{waiting_list_id}", response_model=WaitingList)
def update_waiting_list(
    waiting_list_id: UUID,
    waiting_list: WaitingListUpdate,
    db: Session = Depends(get_db),
):
    """Update a waiting list."""
    updated_waiting_list = WaitingListService(db).update_waiting_list(
        waiting_list_id, waiting_list
    )
    if not updated_waiting_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Waiting list not found"
        )
    return updated_waiting_list


@router.delete("/{waiting_list_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_waiting_list(waiting_list_id: UUID, db: Session = Depends(get_db)):
    """Delete a waiting list."""
    if not WaitingListService(db).delete_waiting_list(waiting_list_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Waiting list not found"
        )


@router.post("/search")
def search_waiting_lists(
    filters: Dict[str, Any],
    db: Session = Depends(get_db),
):
    """Search waiting lists based on dynamic filter criteria."""
    waiting_list_service = WaitingListService(db)
    results = waiting_list_service.search(filters)
    return results


# Member management endpoints


@router.post("/{waiting_list_id}/members")
def add_members_to_waiting_list(
    waiting_list_id: UUID,
    request: AddWaitingListMembersRequest,
    db: Session = Depends(get_db),
):
    """Add contacts to a waiting list."""
    waiting_list_service = WaitingListService(db)

    # Check if waiting list exists
    waiting_list = waiting_list_service.get_waiting_list(waiting_list_id)
    if not waiting_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Waiting list not found"
        )

    # Add contacts
    added_count = waiting_list_service.add_contacts_to_list(
        waiting_list_id, request.contact_ids, request.status
    )

    return {
        "message": f"Successfully added {added_count} contact(s) to the waiting list",
        "added_count": added_count,
        "requested_count": len(request.contact_ids),
    }


@router.delete(
    "/{waiting_list_id}/members/{contact_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_member_from_waiting_list(
    waiting_list_id: UUID,
    contact_id: UUID,
    db: Session = Depends(get_db),
):
    """Remove a contact from a waiting list."""
    waiting_list_service = WaitingListService(db)

    if not waiting_list_service.remove_contact_from_list(waiting_list_id, contact_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Waiting list or contact not found, or contact is not in the list",
        )


@router.get("/{waiting_list_id}/members")
def get_waiting_list_members(waiting_list_id: UUID, db: Session = Depends(get_db)):
    """Get all members of a waiting list with their details."""
    waiting_list_service = WaitingListService(db)

    # Check if waiting list exists
    waiting_list = waiting_list_service.get_waiting_list(waiting_list_id)
    if not waiting_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Waiting list not found"
        )

    members = waiting_list_service.get_all_members_with_details(waiting_list_id)

    return {"waiting_list_id": waiting_list_id, "members": members}


@router.get(
    "/{waiting_list_id}/members/count", response_model=WaitingListMemberCountResponse
)
def get_waiting_list_member_count(waiting_list_id: UUID, db: Session = Depends(get_db)):
    """Get the number of members in a waiting list."""
    waiting_list_service = WaitingListService(db)

    # Check if waiting list exists
    waiting_list = waiting_list_service.get_waiting_list(waiting_list_id)
    if not waiting_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Waiting list not found"
        )

    count = waiting_list_service.get_list_member_count(waiting_list_id)

    return WaitingListMemberCountResponse(waiting_list_id=waiting_list_id, count=count)


@router.put("/{waiting_list_id}/members/{contact_id}/status")
def update_member_status(
    waiting_list_id: UUID,
    contact_id: UUID,
    status: str,
    db: Session = Depends(get_db),
):
    """Update the status of a member on a waiting list."""
    waiting_list_service = WaitingListService(db)

    updated_member = waiting_list_service.update_member_status(
        waiting_list_id, contact_id, status
    )
    if not updated_member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Member not found"
        )

    return {
        "message": "Member status updated successfully",
        "waiting_list_id": waiting_list_id,
        "contact_id": contact_id,
        "status": status,
    }


@router.get("/{waiting_list_id}/members/by-status/{status}")
def get_members_by_status(
    waiting_list_id: UUID, status: str, db: Session = Depends(get_db)
):
    """Get all members with a specific status on a waiting list."""
    waiting_list_service = WaitingListService(db)

    # Check if waiting list exists
    waiting_list = waiting_list_service.get_waiting_list(waiting_list_id)
    if not waiting_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Waiting list not found"
        )

    members = waiting_list_service.get_members_by_status(waiting_list_id, status)

    return {
        "waiting_list_id": waiting_list_id,
        "status": status,
        "members": members,
    }


@router.get("/{waiting_list_id}/members/by-status/{status}/count")
def get_member_count_by_status(
    waiting_list_id: UUID, status: str, db: Session = Depends(get_db)
):
    """Get the count of members with a specific status."""
    waiting_list_service = WaitingListService(db)

    # Check if waiting list exists
    waiting_list = waiting_list_service.get_waiting_list(waiting_list_id)
    if not waiting_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Waiting list not found"
        )

    count = waiting_list_service.get_member_count_by_status(waiting_list_id, status)

    return {
        "waiting_list_id": waiting_list_id,
        "status": status,
        "count": count,
    }


@router.post("/{waiting_list_id}/members/bulk-status")
def update_members_status_bulk(
    waiting_list_id: UUID,
    contact_ids: list[UUID],
    status: str,
    db: Session = Depends(get_db),
):
    """Update the status of multiple members at once."""
    waiting_list_service = WaitingListService(db)

    # Check if waiting list exists
    waiting_list = waiting_list_service.get_waiting_list(waiting_list_id)
    if not waiting_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Waiting list not found"
        )

    updated_count = waiting_list_service.update_members_status_bulk(
        waiting_list_id, contact_ids, status
    )

    return {
        "message": f"Successfully updated {updated_count} member(s)",
        "updated_count": updated_count,
        "requested_count": len(contact_ids),
    }


@router.delete("/{waiting_list_id}/members", status_code=status.HTTP_200_OK)
def clear_waiting_list_members(waiting_list_id: UUID, db: Session = Depends(get_db)):
    """Clear all members from a waiting list."""
    waiting_list_service = WaitingListService(db)

    # Check if waiting list exists
    waiting_list = waiting_list_service.get_waiting_list(waiting_list_id)
    if not waiting_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Waiting list not found"
        )

    removed_count = waiting_list_service.clear_list_members(waiting_list_id)

    return {
        "message": f"Successfully removed {removed_count} contact(s) from the waiting list",
        "removed_count": removed_count,
    }


@router.get("/contacts/{contact_id}/waiting-lists", response_model=list[WaitingList])
def get_waiting_lists_for_contact(contact_id: UUID, db: Session = Depends(get_db)):
    """Get all waiting lists that a contact belongs to."""
    from app.services.contact_service import ContactService

    # Check if contact exists
    contact = ContactService(db).get_contact(contact_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )

    waiting_list_service = WaitingListService(db)
    waiting_lists = waiting_list_service.get_waiting_lists_for_contact(contact_id)

    return waiting_lists


@router.get("/{waiting_list_id}/members/{contact_id}/is-member")
def check_contact_membership(
    waiting_list_id: UUID,
    contact_id: UUID,
    db: Session = Depends(get_db),
):
    """Check if a contact is a member of a waiting list."""
    waiting_list_service = WaitingListService(db)

    # Check if waiting list exists
    waiting_list = waiting_list_service.get_waiting_list(waiting_list_id)
    if not waiting_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Waiting list not found"
        )

    is_member = waiting_list_service.is_contact_in_list(waiting_list_id, contact_id)

    return {
        "waiting_list_id": waiting_list_id,
        "contact_id": contact_id,
        "is_member": is_member,
    }


@router.get("/{waiting_list_id}/members/{contact_id}/status")
def get_member_status(
    waiting_list_id: UUID,
    contact_id: UUID,
    db: Session = Depends(get_db),
):
    """Get the status of a member on a waiting list."""
    waiting_list_service = WaitingListService(db)

    # Check if waiting list exists
    waiting_list = waiting_list_service.get_waiting_list(waiting_list_id)
    if not waiting_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Waiting list not found"
        )

    member = waiting_list_service.get_member_with_status(waiting_list_id, contact_id)
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Member not found"
        )

    return {
        "waiting_list_id": waiting_list_id,
        "contact_id": contact_id,
        "status": member.status,
        "created_at": member.created_at,
        "updated_at": member.updated_at,
    }

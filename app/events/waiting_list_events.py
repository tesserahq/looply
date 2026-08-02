"""
Utilities for building waiting list-related CloudEvents payloads.
"""

from __future__ import annotations

from app.models.waiting_list import WaitingList as WaitingListModel
from app.models.waiting_list_member import WaitingListMember as WaitingListMemberModel
from app.models.contact import Contact as ContactModel
from app.schemas.waiting_list import WaitingList as WaitingListSchema
from app.schemas.contact import Contact as ContactSchema
from tessera_sdk.infra.events.event import Event, event_type, event_source

# Waiting list events
WAITING_LIST_CONTACT_ADDED = "waiting_list.contact_added"


def build_waiting_list_contact_added_event(
    waiting_list: WaitingListModel,
    contact: ContactModel,
    member: WaitingListMemberModel,
) -> Event:
    """Create a CloudEvent for a contact being added to a waiting list."""
    waiting_list_schema = WaitingListSchema.model_validate(waiting_list)
    contact_schema = ContactSchema.model_validate(contact)

    return Event(
        source=event_source(f"/waiting_lists/{waiting_list.id}"),
        event_type=event_type(WAITING_LIST_CONTACT_ADDED),
        event_data={
            "waiting_list": waiting_list_schema.model_dump(mode="json"),
            "contact": contact_schema.model_dump(mode="json"),
            "member": {
                "id": str(member.id),
                "waiting_list_id": str(member.waiting_list_id),
                "contact_id": str(member.contact_id),
                "status": member.status,
                "created_at": (
                    member.created_at.isoformat() if member.created_at else None
                ),
            },
        },
        subject=f"/waiting_list/{waiting_list.id}/contact/{contact.id}",
        user_id=str(contact.created_by_id),
        labels={
            "waiting_list_id": str(waiting_list.id),
            "contact_id": str(contact.id),
            "member_id": str(member.id),
        },
        tags=[
            f"waiting_list_id:{str(waiting_list.id)}",
            f"contact_id:{str(contact.id)}",
            f"member_id:{str(member.id)}",
        ],
    )

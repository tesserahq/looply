"""
Utilities for building contact list-related CloudEvents payloads.
"""

from __future__ import annotations

from typing import Dict, Any
from uuid import UUID

from app.models.contact_list import ContactList as ContactListModel
from app.models.contact_list_member import ContactListMember as ContactListMemberModel
from app.models.contact import Contact as ContactModel
from app.schemas.contact_list import ContactList as ContactListSchema
from app.schemas.contact_list_member import ContactListMember as ContactListMemberSchema
from app.schemas.contact import Contact as ContactSchema
from tessera_sdk.events.event import Event, event_type, event_source

# Contact list events
CONTACT_LIST_SUBSCRIBED = "contact_list.contact_subscribed"
CONTACT_LIST_UNSUBSCRIBED = "contact_list.contact_unsubscribed"


def build_contact_subscribed_event(
    contact_list: ContactListModel,
    contact: ContactModel,
    member: ContactListMemberModel,
) -> Event:
    """Create a CloudEvent for contact list subscription."""
    contact_list_schema = ContactListSchema.model_validate(contact_list)
    contact_schema = ContactSchema.model_validate(contact)
    member_schema = ContactListMemberSchema.model_validate(member)

    return Event(
        source=event_source(f"/contact_lists/{contact_list.id}"),
        event_type=event_type(CONTACT_LIST_SUBSCRIBED),
        event_data={
            "contact_list": contact_list_schema.model_dump(mode="json"),
            "contact": contact_schema.model_dump(mode="json"),
            "member": member_schema.model_dump(mode="json"),
        },
        subject=f"/contact_list/{contact_list.id}/contact/{contact.id}",
        user_id=str(contact.created_by_id),
        labels={
            "contact_list_id": str(contact_list.id),
            "contact_id": str(contact.id),
            "member_id": str(member.id),
        },
        tags=[
            f"contact_list_id:{str(contact_list.id)}",
            f"contact_id:{str(contact.id)}",
            f"member_id:{str(member.id)}",
        ],
    )


def build_contact_unsubscribed_event(
    contact_list: ContactListModel, contact: ContactModel
) -> Event:
    """Create a CloudEvent for contact list unsubscription."""
    contact_list_schema = ContactListSchema.model_validate(contact_list)
    contact_schema = ContactSchema.model_validate(contact)

    return Event(
        source=event_source(f"/contact_lists/{contact_list.id}"),
        event_type=event_type(CONTACT_LIST_UNSUBSCRIBED),
        event_data={
            "contact_list": contact_list_schema.model_dump(mode="json"),
            "contact": contact_schema.model_dump(mode="json"),
        },
        subject=f"/contact_list/{contact_list.id}/contact/{contact.id}",
        user_id=str(contact.created_by_id),
        labels={
            "contact_list_id": str(contact_list.id),
            "contact_id": str(contact.id),
        },
        tags=[
            f"contact_list_id:{str(contact_list.id)}",
            f"contact_id:{str(contact.id)}",
        ],
    )

"""
Utilities for building contact-related CloudEvents payloads.
"""

from __future__ import annotations

from uuid import UUID

from app.models.contact import Contact as ContactModel
from app.schemas.contact import Contact as ContactSchema
from tessera_sdk.events.event import Event, event_type, event_source

# Contact events
CONTACT_CREATED = "contact.created"
CONTACT_UPDATED = "contact.updated"
CONTACT_DELETED = "contact.deleted"


def build_contact_created_event(contact: ContactModel) -> Event:
    """Create a CloudEvent for contact creation."""
    contact_schema = ContactSchema.model_validate(contact)

    return Event(
        source=event_source(f"/contacts/{contact.id}"),
        event_type=event_type(CONTACT_CREATED),
        event_data={
            "contact": contact_schema.model_dump(mode="json"),
        },
        subject=f"/contact/{contact.id}",
        user_id=str(contact.created_by_id),
        labels={
            "contact_id": str(contact.id),
        },
        tags=[
            f"contact_id:{str(contact.id)}",
        ],
    )


def build_contact_updated_event(contact: ContactModel, user_id: UUID) -> Event:
    """Create a CloudEvent for contact update.

    Args:
        contact: The contact that was updated
        user_id: The ID of the user who performed the update
    """
    contact_schema = ContactSchema.model_validate(contact)

    return Event(
        source=event_source(f"/contacts/{contact.id}"),
        event_type=event_type(CONTACT_UPDATED),
        event_data={
            "contact": contact_schema.model_dump(mode="json"),
        },
        subject=f"/contact/{contact.id}",
        user_id=str(user_id),
        labels={
            "contact_id": str(contact.id),
        },
        tags=[
            f"contact_id:{str(contact.id)}",
        ],
    )


def build_contact_deleted_event(contact: ContactModel, user_id: UUID) -> Event:
    """Create a CloudEvent for contact deletion.

    Args:
        contact: The contact that was deleted
        user_id: The ID of the user who performed the deletion
    """
    contact_schema = ContactSchema.model_validate(contact)

    return Event(
        source=event_source(f"/contacts/{contact.id}"),
        event_type=event_type(CONTACT_DELETED),
        event_data={
            "contact": contact_schema.model_dump(mode="json"),
        },
        subject=f"/contact/{contact.id}",
        user_id=str(user_id),
        labels={
            "contact_id": str(contact.id),
        },
        tags=[
            f"contact_id:{str(contact.id)}",
        ],
    )

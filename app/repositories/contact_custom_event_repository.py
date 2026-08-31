from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.contact_custom_event import ContactCustomEvent


class ContactCustomEventRepository:
    """Repository for the append-only per-contact custom event log. No update/delete -
    every ingested event is its own row (see
    docs/prds/0002-contact-custom-fields-and-events.md, "Custom Events").
    """

    def __init__(self, db: Session):
        self.db = db

    def create_event(
        self,
        contact_id: UUID,
        name: str,
        occurred_at: datetime,
        properties: dict,
        raw_envelope: dict,
    ) -> ContactCustomEvent:
        """Record a new event against a contact."""
        event = ContactCustomEvent(
            contact_id=contact_id,
            name=name,
            occurred_at=occurred_at,
            properties=properties,
            raw_envelope=raw_envelope,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def list_events_for_contact(
        self, contact_id: UUID, name: Optional[str] = None
    ) -> List[ContactCustomEvent]:
        """List a contact's event history, most recent first, optionally filtered by
        event name (user story 11)."""
        query = self.db.query(ContactCustomEvent).filter(
            ContactCustomEvent.contact_id == contact_id
        )
        if name is not None:
            query = query.filter(ContactCustomEvent.name == name)
        return query.order_by(ContactCustomEvent.occurred_at.desc()).all()

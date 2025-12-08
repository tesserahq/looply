"""Command to create a contact."""

import logging
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.contact import Contact
from app.schemas.contact import ContactCreate, ContactCreateRequest
from app.services.contact_service import ContactService
from app.events.contact_events import build_contact_created_event
from tessera_sdk.events.nats_router import NatsEventPublisher


class CreateContactCommand:
    """
    Command to create a new contact.
    Validates uniqueness of email and phone, then creates the contact.
    """

    def __init__(
        self,
        db: Session,
        nats_publisher: Optional[NatsEventPublisher] = None,
    ):
        self.db = db
        self.contact_service = ContactService(db)
        self.nats_publisher = (
            nats_publisher if nats_publisher is not None else NatsEventPublisher()
        )
        self.logger = logging.getLogger(__name__)

    def execute(
        self, contact_data: ContactCreateRequest, created_by_id: UUID
    ) -> Contact:
        """
        Execute the command to create a contact.

        Args:
            contact_data: The contact data to create
            created_by_id: The ID of the user creating the contact

        Returns:
            Contact: The created contact

        Raises:
            ValueError: If email already exists
            ValueError: If phone already exists
        """
        try:
            # Check if email already exists
            if contact_data.email and self.contact_service.get_contact_by_email(
                contact_data.email
            ):
                raise ValueError("Email already registered")

            # Check if phone already exists
            if contact_data.phone and self.contact_service.get_contact_by_phone(
                contact_data.phone
            ):
                raise ValueError("Phone number already registered")

            # Create contact
            contact_create = ContactCreate(
                **contact_data.model_dump(),
                created_by_id=created_by_id,
            )

            contact = self.contact_service.create_contact(contact_create)

            if not contact:
                raise ValueError("Failed to create contact")

            # Publish contact created event
            self._publish_contact_created_event(contact)

            return contact

        except ValueError:
            # Re-raise ValueError as-is (these are expected validation errors)
            raise
        except Exception as e:
            # Rollback the transaction if something goes wrong
            self.db.rollback()
            raise Exception(f"Failed to create contact: {str(e)}")

    def _publish_contact_created_event(self, contact: Contact) -> None:
        """
        Publish a contact created event.

        Args:
            contact: The contact that was created
        """
        event = build_contact_created_event(contact)
        if self.nats_publisher is not None:
            try:
                self.nats_publisher.publish_sync(event, event.event_type)
            except Exception:  # pragma: no cover - defensive logging
                self.logger.exception("Failed to publish contact-created event to NATS")

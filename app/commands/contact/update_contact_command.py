"""Command to update a contact."""

import logging
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.contact import Contact
from app.schemas.contact import ContactUpdate
from app.schemas.user import User
from app.services.contact_service import ContactService
from app.events.contact_events import build_contact_updated_event
from tessera_sdk.events.nats_router import NatsEventPublisher


class UpdateContactCommand:
    """
    Command to update an existing contact.
    Validates uniqueness of email and phone, then updates the contact.
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
        self, contact_id: UUID, contact_data: ContactUpdate, current_user: User
    ) -> Contact:
        """
        Execute the command to update a contact.

        Args:
            contact_id: The ID of the contact to update
            contact_data: The contact data to update
            current_user: The user performing the update

        Returns:
            Contact: The updated contact

        Raises:
            ValueError: If email already exists for another contact
            ValueError: If phone already exists for another contact
            ValueError: If contact is not found
        """
        try:
            # Check if contact exists
            existing_contact = self.contact_service.get_contact(contact_id)
            if not existing_contact:
                raise ValueError("Contact not found")

            # Check if email is being updated and already exists
            if contact_data.email:
                contact_with_email = self.contact_service.get_contact_by_email(
                    contact_data.email
                )
                if contact_with_email and contact_with_email.id != contact_id:
                    raise ValueError("Email already registered")

            # Check if phone is being updated and already exists
            if contact_data.phone:
                contact_with_phone = self.contact_service.get_contact_by_phone(
                    contact_data.phone
                )
                if contact_with_phone and contact_with_phone.id != contact_id:
                    raise ValueError("Phone number already registered")

            # Update contact
            updated_contact = self.contact_service.update_contact(
                contact_id, contact_data
            )

            if not updated_contact:
                raise ValueError(f"Failed to update contact {contact_id}")

            # Publish contact updated event
            self._publish_contact_updated_event(updated_contact, current_user.id)

            return updated_contact

        except ValueError:
            # Re-raise ValueError as-is (these are expected validation errors)
            raise
        except Exception as e:
            # Rollback the transaction if something goes wrong
            self.db.rollback()
            raise Exception(f"Failed to update contact: {str(e)}")

    def _publish_contact_updated_event(self, contact: Contact, user_id: UUID) -> None:
        """
        Publish a contact updated event.

        Args:
            contact: The contact that was updated
            user_id: The ID of the user who performed the update
        """
        event = build_contact_updated_event(contact, user_id)
        if self.nats_publisher is not None:
            try:
                self.nats_publisher.publish_sync(event, event.event_type)
            except Exception:  # pragma: no cover - defensive logging
                self.logger.exception("Failed to publish contact-updated event to NATS")

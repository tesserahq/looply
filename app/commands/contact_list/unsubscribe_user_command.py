"""Command to unsubscribe a contact from a public contact list."""

import logging
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.contact_list import ContactList
from app.models.contact import Contact
from app.schemas.user import User
from app.services.contact_list_service import ContactListService
from app.services.contact_service import ContactService
from app.events.contact_list_events import build_contact_unsubscribed_event
from tessera_sdk.events.nats_router import NatsEventPublisher


class UnsubscribeUserCommand:
    """
    Command to unsubscribe a contact from a public contact list.
    Removes the contact_list_member relationship (soft delete).
    """

    def __init__(
        self,
        db: Session,
        nats_publisher: Optional[NatsEventPublisher] = None,
    ):
        self.db = db
        self.contact_list_service = ContactListService(db)
        self.contact_service = ContactService(db)
        self.nats_publisher = (
            nats_publisher if nats_publisher is not None else NatsEventPublisher()
        )
        self.logger = logging.getLogger(__name__)

    def execute(self, contact_list_id: UUID, current_user: User) -> bool:
        """
        Execute the command to unsubscribe a contact from a contact list.

        Args:
            contact_list_id: The ID of the contact list to unsubscribe from
            current_user: The current user whose email will be used to find the contact

        Returns:
            bool: True if the contact was unsubscribed, False if not found

        Raises:
            ValueError: If the contact list is not found
            ValueError: If the contact is not found
        """
        try:
            # Check if contact list exists
            contact_list = self.contact_list_service.get_contact_list(contact_list_id)
            if not contact_list:
                raise ValueError(f"Contact list {contact_list_id} not found")

            # Find contact by email
            if not current_user.email:
                raise ValueError("User email is required to unsubscribe")

            contact = self.contact_service.get_contact_by_email(current_user.email)
            if not contact:
                raise ValueError(f"Contact with email {current_user.email} not found")

            contact_id = contact.id

            # Remove contact from list using the service method
            removed = self.contact_list_service.remove_contact_from_list(
                contact_list_id, contact_id
            )

            if not removed:
                # Not subscribed, return False
                return False

            # Publish unsubscription event
            self._publish_unsubscribed_event(contact_list, contact)

            return True

        except Exception as e:
            # Rollback the transaction if something goes wrong
            self.db.rollback()
            raise Exception(f"Failed to unsubscribe from contact list: {str(e)}")

    def _publish_unsubscribed_event(
        self, contact_list: ContactList, contact: Contact
    ) -> None:
        """
        Publish a contact unsubscribed event.

        Args:
            contact_list: The contact list that was unsubscribed from
            contact: The contact that unsubscribed
        """
        event = build_contact_unsubscribed_event(contact_list, contact)
        if self.nats_publisher is not None:
            try:
                self.nats_publisher.publish_sync(event, event.event_type)
            except Exception:  # pragma: no cover - defensive logging
                self.logger.exception(
                    "Failed to publish contact-unsubscribed event to NATS"
                )

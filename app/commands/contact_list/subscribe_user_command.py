"""Command to subscribe a contact to a public contact list."""

import logging
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.contact_list import ContactList
from app.models.contact_list_member import ContactListMember
from app.models.contact import Contact
from app.schemas.user import User
from app.schemas.contact import ContactCreate
from app.services.contact_list_service import ContactListService
from app.services.contact_service import ContactService
from app.events.contact_list_events import build_contact_subscribed_event
from tessera_sdk.events.nats_router import NatsEventPublisher


class SubscribeUserCommand:
    """
    Command to subscribe a contact to a public contact list.
    Creates a contact_list_member if it doesn't exist.
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

    def execute(self, contact_list_id: UUID, user: User) -> ContactListMember:
        """
        Execute the command to subscribe a contact to a contact list.

        Args:
            contact_list_id: The ID of the contact list to subscribe to
            user: The current user whose email will be used to find or create the contact

        Returns:
            ContactListMember: The created or existing membership

        Raises:
            ValueError: If the contact list is not found
            ValueError: If the user email is not provided
        """
        try:
            # Check if contact list exists
            contact_list = self.contact_list_service.get_contact_list(contact_list_id)
            if not contact_list:
                raise ValueError(f"Contact list {contact_list_id} not found")

            # Validate user email
            if not user.email:
                raise ValueError("User email is required to subscribe")

            # Find or create contact by email
            contact = self.contact_service.get_contact_by_email(user.email)

            if not contact:
                # Create contact from user information
                contact_data = ContactCreate(
                    first_name=user.first_name,
                    last_name=user.last_name,
                    email=user.email,
                    contact_type="personal",  # Default value
                    phone_type="mobile",  # Default value
                    created_by_id=user.id,
                )
                contact = self.contact_service.create_contact(contact_data)

            contact_id = contact.id

            # Check if member already exists
            existing_member = self.contact_list_service.get_contact_list_member(
                contact_list_id, contact_id
            )

            if existing_member:
                # Already subscribed, return existing member
                return existing_member

            # Add contact to list using the service method
            member = self.contact_list_service.add_contact_to_list(
                contact_list_id, contact_id
            )

            if not member:
                # This shouldn't happen after our checks, but handle it gracefully
                raise ValueError(
                    f"Failed to add contact {contact_id} to contact list {contact_list_id}"
                )

            # Publish subscription event
            self._publish_subscribed_event(contact_list, contact, member)

            return member

        except Exception as e:
            # Rollback the transaction if something goes wrong
            self.db.rollback()
            raise Exception(f"Failed to subscribe to contact list: {str(e)}")

    def _publish_subscribed_event(
        self, contact_list: ContactList, contact: Contact, member: ContactListMember
    ) -> None:
        """
        Publish a contact subscribed event.

        Args:
            contact_list: The contact list that was subscribed to
            contact: The contact that subscribed
            member: The contact list member relationship
        """
        event = build_contact_subscribed_event(contact_list, contact, member)
        if self.nats_publisher is not None:
            try:
                self.nats_publisher.publish_sync(event, event.event_type)
            except Exception:  # pragma: no cover - defensive logging
                self.logger.exception(
                    "Failed to publish contact-subscribed event to NATS"
                )

"""Command to delete a contact."""

import logging
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.contact import Contact
from app.schemas.user import User
from app.services.contact_service import ContactService
from app.events.contact_events import build_contact_deleted_event
from tessera_sdk.events.nats_router import NatsEventPublisher


class DeleteContactCommand:
    """
    Command to delete an existing contact.
    Performs a soft delete and publishes a deletion event.
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

    def execute(self, contact_id: UUID, current_user: User) -> bool:
        """
        Execute the command to delete a contact.

        Args:
            contact_id: The ID of the contact to delete
            current_user: The user performing the deletion

        Returns:
            bool: True if the contact was deleted, False otherwise

        Raises:
            ValueError: If contact is not found
        """
        try:
            # Get contact before deletion for event publishing
            contact = self.contact_service.get_contact(contact_id)
            if not contact:
                raise ValueError("Contact not found")

            # Delete contact (soft delete)
            deleted = self.contact_service.delete_contact(contact_id)

            if not deleted:
                raise ValueError(f"Failed to delete contact {contact_id}")

            # Publish contact deleted event
            self._publish_contact_deleted_event(contact, current_user.id)

            return deleted

        except ValueError:
            # Re-raise ValueError as-is (these are expected validation errors)
            raise
        except Exception as e:
            # Rollback the transaction if something goes wrong
            self.db.rollback()
            raise Exception(f"Failed to delete contact: {str(e)}")

    def _publish_contact_deleted_event(self, contact: Contact, user_id: UUID) -> None:
        """
        Publish a contact deleted event.

        Args:
            contact: The contact that was deleted
            user_id: The ID of the user who performed the deletion
        """
        event = build_contact_deleted_event(contact, user_id)
        if self.nats_publisher is not None:
            try:
                self.nats_publisher.publish_sync(event, event.event_type)
            except Exception:  # pragma: no cover - defensive logging
                self.logger.exception("Failed to publish contact-deleted event to NATS")

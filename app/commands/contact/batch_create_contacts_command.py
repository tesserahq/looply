"""Command to batch create contacts."""

import logging
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.contact import Contact
from app.schemas.contact import ContactCreate, ContactCreateRequest
from app.services.contact_service import ContactService
from app.events.contact_events import build_contact_created_event
from tessera_sdk.events.nats_router import NatsEventPublisher


class BatchCreateContactsCommand:
    """
    Command to batch create multiple contacts.
    Validates uniqueness of email and phone for all contacts, then creates them.
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
        self, contacts_data: List[ContactCreateRequest], created_by_id: UUID
    ) -> List[Contact]:
        """
        Execute the command to batch create contacts.

        Args:
            contacts_data: List of contact data to create
            created_by_id: The ID of the user creating the contacts

        Returns:
            List[Contact]: List of created contacts

        Raises:
            ValueError: If any email already exists
            ValueError: If any phone already exists
            ValueError: If there are duplicate emails/phones within the batch
        """
        try:
            if not contacts_data:
                raise ValueError("No contacts provided")

            # Validate all contacts before creating any
            self._validate_contacts(contacts_data)

            # Prepare all contacts for bulk creation
            contact_creates = [
                ContactCreate(**contact_data.model_dump(), created_by_id=created_by_id)
                for contact_data in contacts_data
            ]

            # Bulk create all contacts
            created_contacts = self.contact_service.bulk_create_contacts(
                contact_creates
            )

            if len(created_contacts) != len(contacts_data):
                raise ValueError(
                    f"Failed to create all contacts. Expected {len(contacts_data)}, got {len(created_contacts)}"
                )

            # Publish contact created events for all contacts
            for contact in created_contacts:
                self._publish_contact_created_event(contact)

            return created_contacts

        except ValueError:
            # Re-raise ValueError as-is (these are expected validation errors)
            raise
        except Exception as e:
            # Rollback the transaction if something goes wrong
            self.db.rollback()
            raise Exception(f"Failed to batch create contacts: {str(e)}")

    def _validate_contacts(self, contacts_data: List[ContactCreateRequest]) -> None:
        """
        Validate all contacts before creation.
        Checks for duplicates within the batch and against existing contacts.

        Args:
            contacts_data: List of contact data to validate

        Raises:
            ValueError: If validation fails
        """
        # Track emails and phones within the batch to detect duplicates
        batch_emails = set()
        batch_phones = set()

        for idx, contact_data in enumerate(contacts_data, start=1):
            # Check for duplicate email within batch
            if contact_data.email:
                if contact_data.email in batch_emails:
                    raise ValueError(
                        f"Duplicate email '{contact_data.email}' found in batch at position {idx}"
                    )
                batch_emails.add(contact_data.email)

                # Check if email already exists in database
                if self.contact_service.get_contact_by_email(contact_data.email):
                    raise ValueError(
                        f"Email '{contact_data.email}' already registered (position {idx})"
                    )

            # Check for duplicate phone within batch
            if contact_data.phone:
                if contact_data.phone in batch_phones:
                    raise ValueError(
                        f"Duplicate phone '{contact_data.phone}' found in batch at position {idx}"
                    )
                batch_phones.add(contact_data.phone)

                # Check if phone already exists in database
                if self.contact_service.get_contact_by_phone(contact_data.phone):
                    raise ValueError(
                        f"Phone number '{contact_data.phone}' already registered (position {idx})"
                    )

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

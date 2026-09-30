"""Command to add contacts to a waiting list by email, creating contacts as needed."""

import logging
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.db import on_commit
from app.models.contact import Contact
from app.models.waiting_list import WaitingList
from app.models.waiting_list_member import WaitingListMember
from app.schemas.contact import ContactCreateRequest, ContactType
from app.schemas.waiting_list import WaitingListContactInput
from app.repositories.contact_repository import ContactRepository
from app.repositories.waiting_list_repository import WaitingListRepository
from app.commands.contact.create_contact_command import CreateContactCommand
from app.events.waiting_list_events import build_waiting_list_contact_added_event
from tessera_sdk.infra.events.nats_router import NatsEventPublisher


class AddContactsByEmailToWaitingListCommand:
    """
    Command to add contacts to a waiting list from email-only input.
    For each entry, reuses the existing contact matched by email, or creates
    a new one, then adds that contact to the waiting list.
    """

    def __init__(
        self,
        db: Session,
        nats_publisher: Optional[NatsEventPublisher] = None,
    ):
        self.db = db
        self.contact_repository = ContactRepository(db)
        self.waiting_list_repository = WaitingListRepository(db)
        self.nats_publisher = (
            nats_publisher if nats_publisher is not None else NatsEventPublisher()
        )
        self.create_contact_command = CreateContactCommand(db, self.nats_publisher)
        self.logger = logging.getLogger(__name__)

    def execute(
        self,
        waiting_list_id: UUID,
        contacts: List[WaitingListContactInput],
        status: str,
        created_by_id: UUID,
    ) -> int:
        """
        Find or create a contact for each entry by email, then add it to the waiting list.

        Args:
            waiting_list_id: The ID of the waiting list
            contacts: Email-based contact entries to add
            status: The member status to assign
            created_by_id: The user to record as the creator of any new contacts

        Returns:
            int: Number of contacts successfully added to the waiting list
        """
        waiting_list = self.waiting_list_repository.get_waiting_list(waiting_list_id)
        if not waiting_list:
            return 0

        added_count = 0
        for entry in contacts:
            email = entry.email.strip().lower()
            contact = self.contact_repository.get_contact_by_email(email)

            if not contact:
                contact_data = ContactCreateRequest(
                    first_name=entry.first_name,
                    last_name=entry.last_name,
                    email=email,
                    contact_type=ContactType.PERSONAL,
                    phone_type="",
                )
                contact = self.create_contact_command.execute(
                    contact_data, created_by_id
                )

            member = self.waiting_list_repository.add_contact_to_list(
                waiting_list_id, contact.id, status
            )
            if member:
                self._publish_contact_added_event(waiting_list, contact, member)
                added_count += 1

        return added_count

    def _publish_contact_added_event(
        self,
        waiting_list: WaitingList,
        contact: Contact,
        member: WaitingListMember,
    ) -> None:
        """
        Publish a waiting-list contact-added event.

        Args:
            waiting_list: The waiting list the contact was added to
            contact: The contact that was added
            member: The waiting list membership record
        """
        event = build_waiting_list_contact_added_event(waiting_list, contact, member)
        if self.nats_publisher is not None:
            publisher = self.nats_publisher

            def publish() -> None:
                try:
                    publisher.publish_sync(event, event.event_type)
                except Exception:  # pragma: no cover - defensive logging
                    self.logger.exception(
                        "Failed to publish waiting-list contact-added event to NATS"
                    )

            # Dispatch only after the transaction commits; dropped on rollback.
            on_commit(publish)

"""Command to soft delete many contacts."""

from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.commands.contact.delete_contact_command import DeleteContactCommand
from app.repositories.contact_repository import ContactRepository
from app.schemas.contact import (
    ContactBulkResult,
    ContactBulkSkip,
    ContactBulkSkipReason,
)
from app.schemas.user import User
from tessera_sdk.infra.events.nats_router import NatsEventPublisher


class BulkDeleteContactsCommand:
    """
    Command to soft delete each contact in a selection.
    Contacts that don't exist (or are already deleted) are skipped. Each deletion goes
    through DeleteContactCommand, so it publishes the same contact-deleted event a
    single delete does.
    """

    def __init__(
        self,
        db: Session,
        nats_publisher: Optional[NatsEventPublisher] = None,
    ):
        self.contact_repository = ContactRepository(db)
        self.delete_command = DeleteContactCommand(db, nats_publisher=nats_publisher)

    def execute(self, contact_ids: list[UUID], current_user: User) -> ContactBulkResult:
        """
        Execute the command to bulk delete contacts.

        Args:
            contact_ids: Unique IDs of the contacts to delete
            current_user: The user performing the deletion

        Returns:
            ContactBulkResult: Counts, plus each contact that was skipped and why
        """
        deleted_count = 0
        skipped: list[ContactBulkSkip] = []
        for contact_id in contact_ids:
            if self.contact_repository.get_contact(contact_id) is None:
                skipped.append(
                    ContactBulkSkip(
                        contact_id=contact_id,
                        reason=ContactBulkSkipReason.NOT_FOUND,
                    )
                )
                continue

            self.delete_command.execute(contact_id, current_user)
            deleted_count += 1

        return ContactBulkResult(
            requested_count=len(contact_ids),
            updated_count=deleted_count,
            skipped=skipped,
        )

"""Command to apply attribute changes and added tags to many contacts."""

from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.commands.contact.update_contact_command import UpdateContactCommand
from app.repositories.contact_repository import ContactRepository
from app.repositories.tag_repository import TagRepository
from app.schemas.contact import (
    ContactBulkChanges,
    ContactBulkResult,
    ContactBulkSkip,
    ContactBulkSkipReason,
    ContactUpdate,
)
from app.schemas.user import User
from tessera_sdk.infra.events.nats_router import NatsEventPublisher


class BulkUpdateContactsCommand:
    """
    Command to apply the same changes to each contact in a selection.
    Contacts that don't exist are skipped; the rest are updated. Each contact goes
    through UpdateContactCommand, so it publishes the same contact-updated event a
    single update does. All writes share the request's transaction.
    """

    def __init__(
        self,
        db: Session,
        nats_publisher: Optional[NatsEventPublisher] = None,
    ):
        self.contact_repository = ContactRepository(db)
        self.tag_repository = TagRepository(db)
        self.update_command = UpdateContactCommand(db, nats_publisher=nats_publisher)
        self.db = db

    def execute(
        self,
        contact_ids: list[UUID],
        changes: Optional[ContactBulkChanges],
        add_tags: Optional[list[str]],
        current_user: User,
    ) -> ContactBulkResult:
        """
        Execute the command to bulk update contacts.

        Args:
            contact_ids: Unique IDs of the contacts to update
            changes: Attribute values to set on every contact, or None
            add_tags: Tag names to add to every contact, or None
            current_user: The user performing the update

        Returns:
            ContactBulkResult: Counts, plus each contact that was skipped and why
        """
        update = (
            ContactUpdate(**changes.model_dump(exclude_unset=True))
            if changes
            else ContactUpdate()
        )

        updated_count = 0
        skipped: list[ContactBulkSkip] = []
        for contact_id in contact_ids:
            contact = self.contact_repository.get_contact(contact_id)
            if contact is None:
                skipped.append(
                    ContactBulkSkip(
                        contact_id=contact_id,
                        reason=ContactBulkSkipReason.NOT_FOUND,
                    )
                )
                continue

            if add_tags:
                self.tag_repository.add_contact_tags(
                    contact_id, add_tags, current_user.id
                )
                # Tags are read from the relationship; drop the cached copy so the
                # update event below carries the tags that were just added.
                self.db.expire(contact, ["_tags_rel"])

            self.update_command.execute(contact_id, update, current_user)
            updated_count += 1

        return ContactBulkResult(
            requested_count=len(contact_ids),
            updated_count=updated_count,
            skipped=skipped,
        )

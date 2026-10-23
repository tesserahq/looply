from unittest.mock import Mock

from app.commands.contact.bulk_delete_contacts_command import (
    BulkDeleteContactsCommand,
)
from app.commands.contact.bulk_update_contacts_command import (
    BulkUpdateContactsCommand,
)
from app.schemas.contact import ContactBulkChanges
from app.schemas.user import User


def test_bulk_update_publishes_one_event_per_contact_after_commit(
    db, execution_boundary, test_contact, setup_contact, test_user
):
    publisher = Mock()
    command = BulkUpdateContactsCommand(db, nats_publisher=publisher)

    with execution_boundary():
        command.execute(
            [test_contact.id, setup_contact.id],
            ContactBulkChanges(company="Acme Corp"),
            None,
            User.model_validate(test_user),
        )
        publisher.publish_sync.assert_not_called()

    assert publisher.publish_sync.call_count == 2


def test_bulk_delete_publishes_one_event_per_contact_after_commit(
    db, execution_boundary, test_contact, setup_contact, test_user
):
    publisher = Mock()
    command = BulkDeleteContactsCommand(db, nats_publisher=publisher)

    with execution_boundary():
        command.execute(
            [test_contact.id, setup_contact.id], User.model_validate(test_user)
        )
        publisher.publish_sync.assert_not_called()

    assert publisher.publish_sync.call_count == 2

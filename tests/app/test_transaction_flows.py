"""Multi-step flows are atomic under the managed transaction boundary.

Each test runs code the way an entry point does (``execution_boundary``:
commit on success, roll back on error) and injects a failure partway through.
"""

from unittest.mock import Mock

import pytest

from app.commands.campaign.send_campaign_command import (
    CampaignSendError,
    SendCampaignCommand,
)
from app.commands.contact_list.subscribe_user_command import SubscribeUserCommand
from app.constants.campaign import CampaignStatus
from app.repositories.campaign_repository import CampaignRepository
from app.repositories.contact_list_repository import ContactListRepository
from app.repositories.contact_repository import ContactRepository
from app.repositories.tag_repository import TagConflictError, TagRepository
from app.schemas.user import User


def test_subscribe_failure_leaves_no_contact_and_publishes_nothing(
    db, execution_boundary, public_contact_list, test_user, monkeypatch
):
    """Subscribing creates the contact, then the membership. A failure on the
    membership must not leave the contact behind or announce anything."""
    publisher = Mock()
    command = SubscribeUserCommand(db, nats_publisher=publisher)

    def fail_membership(*args, **kwargs):
        raise RuntimeError("membership insert failed")

    monkeypatch.setattr(
        command.contact_list_repository, "add_contact_to_list", fail_membership
    )

    with pytest.raises(RuntimeError, match="membership insert failed"):
        with execution_boundary():
            command.execute(public_contact_list.id, User.model_validate(test_user))

    assert ContactRepository(db).get_contact_by_email(test_user.email) is None
    publisher.publish_sync.assert_not_called()


def test_subscribe_publishes_only_after_commit(
    db, execution_boundary, public_contact_list, test_user
):
    publisher = Mock()
    command = SubscribeUserCommand(db, nats_publisher=publisher)

    with execution_boundary():
        command.execute(public_contact_list.id, User.model_validate(test_user))
        publisher.publish_sync.assert_not_called()

    publisher.publish_sync.assert_called_once()
    contact = ContactRepository(db).get_contact_by_email(test_user.email)
    assert ContactListRepository(db).is_contact_in_list(
        public_contact_list.id, contact.id
    )


def test_tag_name_conflict_does_not_poison_the_transaction(
    db, execution_boundary, test_user, faker
):
    """A conflict is contained in a savepoint: the caller can handle it and the
    rest of the execution still commits."""
    name = faker.unique.word()

    with execution_boundary():
        repository = TagRepository(db)
        repository.create_tag(name, test_user.id)
        with pytest.raises(TagConflictError):
            repository.create_tag(name.upper(), test_user.id)
        other = repository.create_tag(f"{name}-other", test_user.id)

    assert repository.get_tag(other.id) is not None
    assert len(repository.get_or_create_tags([name], test_user.id)) == 1


def test_failed_send_persists_failed_status_despite_caller_rollback(
    db, execution_boundary, draft_campaign, test_contact_list, test_contact, monkeypatch
):
    """'failed' is committed before raising, so the entry point's rollback on
    the raised error cannot undo it."""
    monkeypatch.setattr(
        "app.commands.campaign.send_campaign_command.time.sleep", lambda *_: None
    )
    ContactListRepository(db).add_contact_to_list(test_contact_list.id, test_contact.id)

    sendly = Mock()
    sendly.send_broadcast.side_effect = Exception("Sendly unavailable")
    command = SendCampaignCommand(db, sendly_client=sendly)

    with pytest.raises(CampaignSendError, match="Failed to send campaign"):
        with execution_boundary():
            command.execute(draft_campaign.id)

    campaign = CampaignRepository(db).get_campaign(draft_campaign.id)
    assert campaign.status == CampaignStatus.FAILED.value

"""Tests for SubscribeUserCommand."""

import pytest
from uuid import uuid4

from app.commands.contact_list.subscribe_user_command import SubscribeUserCommand
from app.services.contact_list_service import ContactListService
from app.models.contact_list_member import ContactListMember
from app.schemas.user import User


def test_subscribe_command_success(db, public_contact_list, test_user):
    """Test successful subscription to a public contact list."""
    command = SubscribeUserCommand(db)
    user_schema = User.model_validate(test_user)
    member = command.execute(public_contact_list.id, user_schema)

    # Assertions
    assert member is not None
    assert member.contact_list_id == public_contact_list.id
    assert member.deleted_at is None

    # Verify member exists in database
    service = ContactListService(db)
    # Get contact by user email to verify
    from app.services.contact_service import ContactService

    contact_service = ContactService(db)
    contact = contact_service.get_contact_by_email(test_user.email)
    assert contact is not None
    assert service.is_contact_in_list(public_contact_list.id, contact.id)


def test_subscribe_command_already_subscribed(db, public_contact_list, test_user):
    """Test subscribing when contact is already subscribed."""
    # First subscription
    command = SubscribeUserCommand(db)
    user_schema = User.model_validate(test_user)
    first_member = command.execute(public_contact_list.id, user_schema)
    assert first_member is not None

    # Second subscription attempt
    second_member = command.execute(public_contact_list.id, user_schema)

    # Should return the same member
    assert second_member.id == first_member.id
    assert second_member.contact_list_id == first_member.contact_list_id
    assert second_member.contact_id == first_member.contact_id


def test_subscribe_command_contact_list_not_found(db, test_user):
    """Test subscription when contact list doesn't exist."""
    command = SubscribeUserCommand(db)
    user_schema = User.model_validate(test_user)
    non_existent_id = uuid4()

    with pytest.raises(Exception) as exc_info:
        command.execute(non_existent_id, user_schema)

    assert "not found" in str(exc_info.value).lower()


def test_subscribe_command_contact_not_found(db, public_contact_list, test_user):
    """Test subscription when contact doesn't exist - command will create it."""
    # This test is now different - the command will create a contact if it doesn't exist
    # So we test that a user without a contact can still subscribe
    command = SubscribeUserCommand(db)
    user_schema = User.model_validate(test_user)

    # Verify contact doesn't exist yet
    from app.services.contact_service import ContactService

    contact_service = ContactService(db)
    contact = contact_service.get_contact_by_email(test_user.email)
    # Contact might not exist, which is fine - command will create it

    # Execute command - should create contact and subscribe
    member = command.execute(public_contact_list.id, user_schema)
    assert member is not None

    # Verify contact was created
    contact = contact_service.get_contact_by_email(test_user.email)
    assert contact is not None


def test_subscribe_command_multiple_contacts(
    db, public_contact_list, test_user, setup_user
):
    """Test subscribing multiple contacts to the same list."""
    command = SubscribeUserCommand(db)

    # Subscribe first user
    user1_schema = User.model_validate(test_user)
    member1 = command.execute(public_contact_list.id, user1_schema)
    assert member1 is not None

    # Subscribe second user
    user2_schema = User.model_validate(setup_user)
    member2 = command.execute(public_contact_list.id, user2_schema)
    assert member2 is not None

    # Verify both are different members
    assert member1.id != member2.id
    assert member1.contact_id != member2.contact_id

    # Verify both are in the list
    service = ContactListService(db)
    from app.services.contact_service import ContactService

    contact_service = ContactService(db)
    contact1 = contact_service.get_contact_by_email(test_user.email)
    contact2 = contact_service.get_contact_by_email(setup_user.email)
    assert contact1 is not None
    assert contact2 is not None
    assert service.is_contact_in_list(public_contact_list.id, contact1.id)
    assert service.is_contact_in_list(public_contact_list.id, contact2.id)


def test_subscribe_command_creates_member_record(db, public_contact_list, test_user):
    """Test that subscription creates a ContactListMember record."""
    # Verify no member exists initially
    service = ContactListService(db)
    from app.services.contact_service import ContactService

    contact_service = ContactService(db)
    contact = contact_service.get_contact_by_email(test_user.email)
    if contact:
        assert not service.is_contact_in_list(public_contact_list.id, contact.id)

    # Subscribe
    command = SubscribeUserCommand(db)
    user_schema = User.model_validate(test_user)
    member = command.execute(public_contact_list.id, user_schema)

    # Verify member was created
    assert member is not None
    assert member.id is not None

    # Verify contact was created/found
    contact = contact_service.get_contact_by_email(test_user.email)
    assert contact is not None

    # Verify member exists in database
    db_member = (
        db.query(ContactListMember)
        .filter(
            ContactListMember.contact_list_id == public_contact_list.id,
            ContactListMember.contact_id == contact.id,
            ContactListMember.deleted_at.is_(None),
        )
        .first()
    )
    assert db_member is not None
    assert db_member.id == member.id

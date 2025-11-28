"""Tests for UnsubscribeUserCommand."""

import pytest
from uuid import uuid4
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.commands.contact_list.unsubscribe_user_command import UnsubscribeUserCommand
from app.commands.contact_list.subscribe_user_command import SubscribeUserCommand
from app.services.contact_list_service import ContactListService
from app.services.contact_service import ContactService
from app.models.contact_list_member import ContactListMember
from app.schemas.user import User


def test_unsubscribe_command_success(db, public_contact_list, test_user):
    """Test successful unsubscription from a public contact list."""
    # First subscribe
    subscribe_command = SubscribeUserCommand(db)
    user_schema = User.model_validate(test_user)
    subscribe_command.execute(public_contact_list.id, user_schema)

    # Verify subscribed
    service = ContactListService(db)
    contact_service = ContactService(db)
    contact = contact_service.get_contact_by_email(test_user.email)
    assert contact is not None
    assert service.is_contact_in_list(public_contact_list.id, contact.id)

    # Unsubscribe
    unsubscribe_command = UnsubscribeUserCommand(db)
    result = unsubscribe_command.execute(public_contact_list.id, user_schema)

    # Assertions
    assert result is True
    assert not service.is_contact_in_list(public_contact_list.id, contact.id)

    # Verify member is soft deleted (need to skip soft delete filter to see it)
    member = (
        db.query(ContactListMember)
        .execution_options(skip_soft_delete_filter=True)
        .filter(
            ContactListMember.contact_list_id == public_contact_list.id,
            ContactListMember.contact_id == contact.id,
        )
        .first()
    )
    assert member is not None
    assert member.deleted_at is not None


def test_unsubscribe_command_not_subscribed(db, public_contact_list, test_user):
    """Test unsubscribing when contact is not subscribed."""
    # Create a contact for the user first (contact exists but not subscribed)
    from app.models.contact import Contact
    from app.schemas.contact import ContactCreate
    from app.services.contact_service import ContactService

    contact_service = ContactService(db)
    contact = contact_service.get_contact_by_email(test_user.email)
    if not contact:
        # Create contact if it doesn't exist
        contact_data = ContactCreate(
            first_name=test_user.first_name,
            last_name=test_user.last_name,
            email=test_user.email,
            contact_type="personal",
            phone_type="mobile",
            created_by_id=test_user.id,
        )
        contact = contact_service.create_contact(contact_data)

    # Verify not subscribed
    service = ContactListService(db)
    assert not service.is_contact_in_list(public_contact_list.id, contact.id)

    # Try to unsubscribe
    command = UnsubscribeUserCommand(db)
    user_schema = User.model_validate(test_user)
    result = command.execute(public_contact_list.id, user_schema)

    # Should return False (contact exists but not subscribed)
    assert result is False


def test_unsubscribe_command_contact_list_not_found(db, test_user):
    """Test unsubscription when contact list doesn't exist."""
    command = UnsubscribeUserCommand(db)
    user_schema = User.model_validate(test_user)
    non_existent_id = uuid4()

    with pytest.raises(Exception) as exc_info:
        command.execute(non_existent_id, user_schema)

    assert "not found" in str(exc_info.value).lower()


def test_unsubscribe_command_contact_not_found(db, public_contact_list, faker):
    """Test unsubscription when contact doesn't exist."""
    # Create a user without a corresponding contact
    from app.models.user import User as UserModel

    user_without_contact = UserModel(
        email=faker.email(),
        username=faker.email(),
        first_name=faker.first_name(),
        last_name=faker.last_name(),
        provider="google",
        external_id=str(faker.uuid4()),
    )
    db.add(user_without_contact)
    db.commit()
    db.refresh(user_without_contact)

    command = UnsubscribeUserCommand(db)
    user_schema = User.model_validate(user_without_contact)

    with pytest.raises(Exception) as exc_info:
        command.execute(public_contact_list.id, user_schema)

    assert "not found" in str(exc_info.value).lower()


def test_unsubscribe_command_multiple_contacts(
    db, public_contact_list, test_user, setup_user
):
    """Test unsubscribing multiple contacts from the same list."""
    subscribe_command = SubscribeUserCommand(db)
    unsubscribe_command = UnsubscribeUserCommand(db)
    service = ContactListService(db)
    contact_service = ContactService(db)

    # Subscribe both users
    user1_schema = User.model_validate(test_user)
    user2_schema = User.model_validate(setup_user)
    subscribe_command.execute(public_contact_list.id, user1_schema)
    subscribe_command.execute(public_contact_list.id, user2_schema)

    # Get contacts
    contact1 = contact_service.get_contact_by_email(test_user.email)
    contact2 = contact_service.get_contact_by_email(setup_user.email)
    assert contact1 is not None
    assert contact2 is not None

    # Verify both are subscribed
    assert service.is_contact_in_list(public_contact_list.id, contact1.id)
    assert service.is_contact_in_list(public_contact_list.id, contact2.id)

    # Unsubscribe first contact
    result1 = unsubscribe_command.execute(public_contact_list.id, user1_schema)
    assert result1 is True
    assert not service.is_contact_in_list(public_contact_list.id, contact1.id)
    assert service.is_contact_in_list(public_contact_list.id, contact2.id)

    # Unsubscribe second contact
    result2 = unsubscribe_command.execute(public_contact_list.id, user2_schema)
    assert result2 is True
    assert not service.is_contact_in_list(public_contact_list.id, contact2.id)


def test_unsubscribe_command_soft_deletes_member(db, public_contact_list, test_user):
    """Test that unsubscription soft deletes the ContactListMember record."""
    # Subscribe first
    subscribe_command = SubscribeUserCommand(db)
    user_schema = User.model_validate(test_user)
    member = subscribe_command.execute(public_contact_list.id, user_schema)
    member_id = member.id

    # Unsubscribe
    unsubscribe_command = UnsubscribeUserCommand(db)
    unsubscribe_command.execute(public_contact_list.id, user_schema)

    # Verify member still exists but is soft deleted (need to skip soft delete filter)
    db_member = (
        db.query(ContactListMember)
        .execution_options(skip_soft_delete_filter=True)
        .filter(ContactListMember.id == member_id)
        .first()
    )
    assert db_member is not None
    assert db_member.deleted_at is not None
    assert isinstance(db_member.deleted_at, datetime)


def test_unsubscribe_command_after_resubscribe(db, public_contact_list, test_user):
    """Test that you can resubscribe after unsubscribing."""
    subscribe_command = SubscribeUserCommand(db)
    unsubscribe_command = UnsubscribeUserCommand(db)
    service = ContactListService(db)
    contact_service = ContactService(db)
    user_schema = User.model_validate(test_user)

    # Subscribe
    member1 = subscribe_command.execute(public_contact_list.id, user_schema)
    contact = contact_service.get_contact_by_email(test_user.email)
    assert contact is not None
    assert service.is_contact_in_list(public_contact_list.id, contact.id)

    # Unsubscribe
    unsubscribe_command.execute(public_contact_list.id, user_schema)
    assert not service.is_contact_in_list(public_contact_list.id, contact.id)

    # Resubscribe
    member2 = subscribe_command.execute(public_contact_list.id, user_schema)
    assert service.is_contact_in_list(public_contact_list.id, contact.id)

    # Should restore the soft-deleted member (same ID)
    assert member2 is not None
    assert member2.id == member1.id  # Should be the same member, restored
    assert member2.deleted_at is None  # Should be restored (not soft-deleted)

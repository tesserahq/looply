from uuid import uuid4
from sqlalchemy.orm import Session
from app.services.contact_list_service import ContactListService
from app.models.contact_list import ContactList
from app.models.contact import Contact


def test_add_contact_to_list(db, test_contact_list, test_contact):
    """Test adding a contact to a contact list."""
    service = ContactListService(db)

    member = service.add_contact_to_list(test_contact_list.id, test_contact.id)

    assert member is not None
    assert member.contact_list_id == test_contact_list.id
    assert member.contact_id == test_contact.id
    assert member.deleted_at is None


def test_add_contact_to_list_already_exists(db, test_contact_list, test_contact):
    """Test adding a contact to a list when it already exists."""
    service = ContactListService(db)

    # Add once
    member1 = service.add_contact_to_list(test_contact_list.id, test_contact.id)
    assert member1 is not None

    # Try to add again
    member2 = service.add_contact_to_list(test_contact_list.id, test_contact.id)
    assert member2 is None


def test_add_contact_to_nonexistent_list(db, test_contact):
    """Test adding a contact to a non-existent list."""
    service = ContactListService(db)
    nonexistent_list_id = uuid4()

    member = service.add_contact_to_list(nonexistent_list_id, test_contact.id)
    assert member is None


def test_add_nonexistent_contact_to_list(db, test_contact_list):
    """Test adding a non-existent contact to a list."""
    service = ContactListService(db)
    nonexistent_contact_id = uuid4()

    member = service.add_contact_to_list(test_contact_list.id, nonexistent_contact_id)
    assert member is None


def test_remove_contact_from_list(db, test_contact_list, test_contact):
    """Test removing a contact from a contact list."""
    service = ContactListService(db)

    # Add the contact first
    service.add_contact_to_list(test_contact_list.id, test_contact.id)

    # Remove it
    success = service.remove_contact_from_list(test_contact_list.id, test_contact.id)
    assert success is True

    # Verify it's removed (check member count is 0)
    count = service.get_list_member_count(test_contact_list.id)
    assert count == 0


def test_remove_contact_from_list_not_found(db, test_contact_list):
    """Test removing a contact that's not in the list."""
    service = ContactListService(db)
    nonexistent_contact_id = uuid4()

    success = service.remove_contact_from_list(
        test_contact_list.id, nonexistent_contact_id
    )
    assert success is False


def test_get_list_members(db, test_contact_list, test_contact, faker, test_user):
    """Test getting all members of a contact list."""
    service = ContactListService(db)

    # Create another contact
    another_contact = Contact(
        first_name=faker.first_name(),
        last_name=faker.last_name(),
        contact_type="business",
        phone_type="work",
        phone=faker.phone_number(),
        email=faker.email(),
        created_by_id=test_user.id,
    )
    db.add(another_contact)
    db.commit()
    db.refresh(another_contact)

    # Add both contacts to the list
    service.add_contact_to_list(test_contact_list.id, test_contact.id)
    service.add_contact_to_list(test_contact_list.id, another_contact.id)

    # Get members
    members = service.get_list_members(test_contact_list.id)

    assert len(members) == 2
    member_ids = [member.id for member in members]
    assert test_contact.id in member_ids
    assert another_contact.id in member_ids


def test_get_list_members_empty(db, test_contact_list):
    """Test getting members from an empty list."""
    service = ContactListService(db)

    members = service.get_list_members(test_contact_list.id)
    assert len(members) == 0


def test_get_list_member_count(db, test_contact_list, test_contact, faker, test_user):
    """Test getting the count of members in a list."""
    service = ContactListService(db)

    # Initially should be 0
    count = service.get_list_member_count(test_contact_list.id)
    assert count == 0

    # Add a contact
    service.add_contact_to_list(test_contact_list.id, test_contact.id)
    count = service.get_list_member_count(test_contact_list.id)
    assert count == 1

    # Add another contact
    another_contact = Contact(
        first_name=faker.first_name(),
        last_name=faker.last_name(),
        contact_type="business",
        phone_type="work",
        phone=faker.phone_number(),
        email=faker.email(),
        created_by_id=test_user.id,
    )
    db.add(another_contact)
    db.commit()
    db.refresh(another_contact)

    service.add_contact_to_list(test_contact_list.id, another_contact.id)
    count = service.get_list_member_count(test_contact_list.id)
    assert count == 2


def test_is_contact_in_list(db, test_contact_list, test_contact):
    """Test checking if a contact is in a list."""
    service = ContactListService(db)

    # Initially not in list
    assert service.is_contact_in_list(test_contact_list.id, test_contact.id) is False

    # Add to list
    service.add_contact_to_list(test_contact_list.id, test_contact.id)

    # Now should be in list
    assert service.is_contact_in_list(test_contact_list.id, test_contact.id) is True


def test_is_contact_in_list_after_removal(db, test_contact_list, test_contact):
    """Test checking if contact is in list after removal."""
    service = ContactListService(db)

    # Add and then remove
    service.add_contact_to_list(test_contact_list.id, test_contact.id)
    service.remove_contact_from_list(test_contact_list.id, test_contact.id)

    # Should not be in list
    assert service.is_contact_in_list(test_contact_list.id, test_contact.id) is False


def test_get_contact_lists_for_contact(
    db, test_contact_list, test_contact, faker, test_user
):
    """Test getting all contact lists that a contact belongs to."""
    service = ContactListService(db)

    # Create another contact list
    another_list = ContactList(
        name=faker.company(),
        description=faker.text(max_nb_chars=100),
        created_by_id=test_user.id,
    )
    db.add(another_list)
    db.commit()
    db.refresh(another_list)

    # Add contact to both lists
    service.add_contact_to_list(test_contact_list.id, test_contact.id)
    service.add_contact_to_list(another_list.id, test_contact.id)

    # Get lists for contact
    lists = service.get_contact_lists_for_contact(test_contact.id)

    assert len(lists) == 2
    list_ids = [contact_list.id for contact_list in lists]
    assert test_contact_list.id in list_ids
    assert another_list.id in list_ids


def test_get_contact_lists_for_contact_without_lists(db, test_contact):
    """Test getting lists for a contact that's not in any list."""
    service = ContactListService(db)

    lists = service.get_contact_lists_for_contact(test_contact.id)
    assert len(lists) == 0


def test_add_multiple_contacts_to_list(
    db, test_contact_list, test_contact, faker, test_user
):
    """Test adding multiple contacts to a list at once."""
    service = ContactListService(db)

    # Create more contacts
    contact2 = Contact(
        first_name=faker.first_name(),
        last_name=faker.last_name(),
        contact_type="business",
        phone_type="work",
        phone=faker.phone_number(),
        email=faker.email(),
        created_by_id=test_user.id,
    )
    contact3 = Contact(
        first_name=faker.first_name(),
        last_name=faker.last_name(),
        contact_type="business",
        phone_type="work",
        phone=faker.phone_number(),
        email=faker.email(),
        created_by_id=test_user.id,
    )
    db.add_all([contact2, contact3])
    db.commit()
    db.refresh(contact2)
    db.refresh(contact3)

    # Add all contacts
    added_count = service.add_contacts_to_list(
        test_contact_list.id, [test_contact.id, contact2.id, contact3.id]
    )

    assert added_count == 3

    # Verify they're all in the list
    members = service.get_list_members(test_contact_list.id)
    assert len(members) == 3


def test_remove_multiple_contacts_from_list(
    db, test_contact_list, test_contact, faker, test_user
):
    """Test removing multiple contacts from a list."""
    service = ContactListService(db)

    # Create and add contacts
    contact2 = Contact(
        first_name=faker.first_name(),
        last_name=faker.last_name(),
        contact_type="business",
        phone_type="work",
        phone=faker.phone_number(),
        email=faker.email(),
        created_by_id=test_user.id,
    )
    db.add(contact2)
    db.commit()
    db.refresh(contact2)

    service.add_contact_to_list(test_contact_list.id, test_contact.id)
    service.add_contact_to_list(test_contact_list.id, contact2.id)

    # Remove all
    removed_count = service.remove_contacts_from_list(
        test_contact_list.id, [test_contact.id, contact2.id]
    )

    assert removed_count == 2

    # Verify list is empty
    members = service.get_list_members(test_contact_list.id)
    assert len(members) == 0


def test_clear_list_members(db, test_contact_list, test_contact, faker, test_user):
    """Test clearing all members from a list."""
    service = ContactListService(db)

    # Create and add multiple contacts
    contact2 = Contact(
        first_name=faker.first_name(),
        last_name=faker.last_name(),
        contact_type="business",
        phone_type="work",
        phone=faker.phone_number(),
        email=faker.email(),
        created_by_id=test_user.id,
    )
    contact3 = Contact(
        first_name=faker.first_name(),
        last_name=faker.last_name(),
        contact_type="business",
        phone_type="work",
        phone=faker.phone_number(),
        email=faker.email(),
        created_by_id=test_user.id,
    )
    db.add_all([contact2, contact3])
    db.commit()
    db.refresh(contact2)
    db.refresh(contact3)

    service.add_contact_to_list(test_contact_list.id, test_contact.id)
    service.add_contact_to_list(test_contact_list.id, contact2.id)
    service.add_contact_to_list(test_contact_list.id, contact3.id)

    # Clear all
    removed_count = service.clear_list_members(test_contact_list.id)
    assert removed_count == 3

    # Verify list is empty
    members = service.get_list_members(test_contact_list.id)
    assert len(members) == 0


def test_clear_empty_list(db, test_contact_list):
    """Test clearing members from an already empty list."""
    service = ContactListService(db)

    removed_count = service.clear_list_members(test_contact_list.id)
    assert removed_count == 0

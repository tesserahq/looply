import pytest
from uuid import uuid4
from datetime import datetime
from sqlalchemy.orm import Session
from app.schemas.contact import ContactCreate, ContactUpdate
from app.services.contact_service import ContactService


@pytest.fixture
def sample_contact_data(faker, test_user):
    return {
        "first_name": faker.first_name(),
        "last_name": faker.last_name(),
        "company": faker.company(),
        "job": faker.job(),
        "contact_type": "business",
        "phone_type": "work",
        "phone": faker.phone_number(),
        "email": faker.email(),
        "website": faker.url(),
        "address_line_1": faker.street_address(),
        "city": faker.city(),
        "state": faker.state(),
        "zip_code": faker.zipcode(),
        "country": faker.country(),
        "notes": faker.text(max_nb_chars=200),
        "is_active": True,
        "created_by_id": test_user.id,
    }


@pytest.fixture
def minimal_contact_data(faker, test_user):
    return {
        "contact_type": "personal",
        "phone_type": "mobile",
        "created_by_id": test_user.id,
    }


def test_create_contact(db: Session, sample_contact_data):
    """Test creating a contact with full data."""
    contact_create = ContactCreate(**sample_contact_data)
    contact = ContactService(db).create_contact(contact_create)

    # Assertions
    assert contact.id is not None
    assert contact.first_name == sample_contact_data["first_name"]
    assert contact.last_name == sample_contact_data["last_name"]
    assert contact.company == sample_contact_data["company"]
    assert contact.job == sample_contact_data["job"]
    assert contact.contact_type == sample_contact_data["contact_type"]
    assert contact.phone_type == sample_contact_data["phone_type"]
    assert contact.phone == sample_contact_data["phone"]
    assert contact.email == sample_contact_data["email"]
    assert contact.website == sample_contact_data["website"]
    assert contact.address_line_1 == sample_contact_data["address_line_1"]
    assert contact.city == sample_contact_data["city"]
    assert contact.state == sample_contact_data["state"]
    assert contact.zip_code == sample_contact_data["zip_code"]
    assert contact.country == sample_contact_data["country"]
    assert contact.notes == sample_contact_data["notes"]
    assert contact.is_active == sample_contact_data["is_active"]
    assert contact.created_by_id == sample_contact_data["created_by_id"]
    assert contact.created_at is not None
    assert contact.updated_at is not None


def test_create_contact_minimal_data(db: Session, minimal_contact_data):
    """Test creating a contact with minimal required data."""
    contact_create = ContactCreate(**minimal_contact_data)
    contact = ContactService(db).create_contact(contact_create)

    # Assertions
    assert contact.id is not None
    assert contact.first_name is None
    assert contact.last_name is None
    assert contact.contact_type == minimal_contact_data["contact_type"]
    assert contact.phone_type == minimal_contact_data["phone_type"]
    assert contact.created_by_id == minimal_contact_data["created_by_id"]
    assert contact.is_active is True  # Default value
    assert contact.created_at is not None
    assert contact.updated_at is not None


def test_get_contact(db: Session, test_contact):
    """Test retrieving a contact by ID."""
    retrieved_contact = ContactService(db).get_contact(test_contact.id)

    # Assertions
    assert retrieved_contact is not None
    assert retrieved_contact.id == test_contact.id
    assert retrieved_contact.first_name == test_contact.first_name
    assert retrieved_contact.email == test_contact.email


def test_get_contact_by_email(db: Session, test_contact):
    """Test retrieving a contact by email."""
    retrieved_contact = ContactService(db).get_contact_by_email(test_contact.email)

    # Assertions
    assert retrieved_contact is not None
    assert retrieved_contact.id == test_contact.id
    assert retrieved_contact.email == test_contact.email


def test_get_contact_by_phone(db: Session, test_contact):
    """Test retrieving a contact by phone."""
    retrieved_contact = ContactService(db).get_contact_by_phone(test_contact.phone)

    # Assertions
    assert retrieved_contact is not None
    assert retrieved_contact.id == test_contact.id
    assert retrieved_contact.phone == test_contact.phone


def test_get_contacts(db: Session, test_contact):
    """Test retrieving all contacts with pagination."""
    contacts = ContactService(db).get_contacts()

    # Assertions
    assert len(contacts) >= 1
    assert any(c.id == test_contact.id for c in contacts)


def test_get_contacts_by_creator(db: Session, test_contact):
    """Test retrieving contacts by creator."""
    contacts = ContactService(db).get_contacts_by_creator(test_contact.created_by_id)

    # Assertions
    assert len(contacts) >= 1
    assert any(c.id == test_contact.id for c in contacts)
    assert all(c.created_by_id == test_contact.created_by_id for c in contacts)


def test_get_active_contacts(db: Session, test_contact, inactive_contact):
    """Test retrieving only active contacts."""
    active_contacts = ContactService(db).get_active_contacts()

    # Assertions
    assert len(active_contacts) >= 1
    assert any(c.id == test_contact.id for c in active_contacts)
    assert not any(c.id == inactive_contact.id for c in active_contacts)
    assert all(c.is_active is True for c in active_contacts)


def test_update_contact(db: Session, test_contact):
    """Test updating a contact."""
    update_data = {
        "first_name": "Updated",
        "last_name": "Name",
        "email": "updated@example.com",
        "company": "New Company",
    }
    contact_update = ContactUpdate(**update_data)

    # Update contact
    updated_contact = ContactService(db).update_contact(test_contact.id, contact_update)

    # Assertions
    assert updated_contact is not None
    assert updated_contact.id == test_contact.id
    assert updated_contact.first_name == update_data["first_name"]
    assert updated_contact.last_name == update_data["last_name"]
    assert updated_contact.email == update_data["email"]
    assert updated_contact.company == update_data["company"]
    # Verify other fields remain unchanged
    assert updated_contact.phone == test_contact.phone
    assert updated_contact.created_by_id == test_contact.created_by_id


def test_update_contact_partial(db: Session, test_contact):
    """Test updating a contact with partial data."""
    update_data = {"first_name": "Only First Name Updated"}
    contact_update = ContactUpdate(**update_data)

    # Update contact
    updated_contact = ContactService(db).update_contact(test_contact.id, contact_update)

    # Assertions
    assert updated_contact is not None
    assert updated_contact.first_name == update_data["first_name"]
    # Verify other fields remain unchanged
    assert updated_contact.last_name == test_contact.last_name
    assert updated_contact.email == test_contact.email
    assert updated_contact.company == test_contact.company


def test_delete_contact(db: Session, test_contact):
    """Test soft deleting a contact."""
    contact_service = ContactService(db)

    # Delete contact
    success = contact_service.delete_contact(test_contact.id)

    # Assertions
    assert success is True
    deleted_contact = contact_service.get_contact(test_contact.id)
    assert deleted_contact is None


def test_contact_not_found_cases(db: Session):
    """Test various not found cases."""
    contact_service = ContactService(db)
    non_existent_id = uuid4()

    # Get non-existent contact
    assert contact_service.get_contact(non_existent_id) is None

    # Get by non-existent email
    assert contact_service.get_contact_by_email("nonexistent@example.com") is None

    # Get by non-existent phone
    assert contact_service.get_contact_by_phone("+1234567890") is None

    # Update non-existent contact
    update_data = {"first_name": "Updated"}
    contact_update = ContactUpdate(**update_data)
    assert contact_service.update_contact(non_existent_id, contact_update) is None

    # Delete non-existent contact
    assert contact_service.delete_contact(non_existent_id) is False


def test_search_contacts_with_filters(db: Session, test_contact):
    """Test searching contacts with dynamic filters."""
    # Search using ilike filter on first name
    filters = {
        "first_name": {"operator": "ilike", "value": f"%{test_contact.first_name[:3]}%"}
    }
    results = ContactService(db).search(filters)

    assert isinstance(results, list)
    assert any(contact.id == test_contact.id for contact in results)

    # Search using exact match
    filters = {"email": test_contact.email}
    results = ContactService(db).search(filters)

    assert len(results) == 1
    assert results[0].id == test_contact.id

    # Search with no match
    filters = {"first_name": {"operator": "==", "value": "nonexistent"}}
    results = ContactService(db).search(filters)

    assert len(results) == 0


def test_search_contacts_by_company(db: Session, test_contact):
    """Test searching contacts by company."""
    filters = {
        "company": {"operator": "ilike", "value": f"%{test_contact.company[:5]}%"}
    }
    results = ContactService(db).search(filters)

    assert isinstance(results, list)
    assert any(contact.id == test_contact.id for contact in results)


def test_search_contacts_by_contact_type(db: Session, test_contact):
    """Test searching contacts by contact type."""
    filters = {"contact_type": test_contact.contact_type}
    results = ContactService(db).search(filters)

    assert isinstance(results, list)
    assert any(contact.id == test_contact.id for contact in results)


def test_toggle_contact_active_status(db: Session, test_contact):
    """Test toggling contact active status."""
    contact_service = ContactService(db)
    original_status = test_contact.is_active

    # Toggle status
    updated_contact = contact_service.toggle_contact_active_status(test_contact.id)

    # Assertions
    assert updated_contact is not None
    assert updated_contact.is_active != original_status
    assert updated_contact.id == test_contact.id


def test_toggle_contact_active_status_not_found(db: Session):
    """Test toggling contact active status for non-existent contact."""
    contact_service = ContactService(db)
    non_existent_id = uuid4()

    # Toggle status
    updated_contact = contact_service.toggle_contact_active_status(non_existent_id)

    # Assertions
    assert updated_contact is None


def test_contact_full_name_property(db: Session, test_contact):
    """Test the full_name property of the contact."""
    # Test with all name parts
    expected_full_name = f"{test_contact.first_name} {test_contact.last_name}"
    assert test_contact.full_name == expected_full_name

    # Test with middle name
    test_contact.middle_name = "Middle"
    expected_with_middle = f"{test_contact.first_name} Middle {test_contact.last_name}"
    assert test_contact.full_name == expected_with_middle

    # Test with None values
    test_contact.first_name = None
    test_contact.last_name = None
    test_contact.middle_name = None
    assert test_contact.full_name == ""


def test_contact_display_name_property(db: Session, test_contact):
    """Test the display_name property of the contact."""
    assert test_contact.display_name == test_contact.full_name


def test_restore_contact(db: Session, test_contact):
    """Test restoring a soft-deleted contact."""
    contact_service = ContactService(db)

    # First delete the contact
    contact_service.delete_contact(test_contact.id)
    assert contact_service.get_contact(test_contact.id) is None

    # Then restore it
    success = contact_service.restore_contact(test_contact.id)
    assert success is True

    # Verify it's restored
    restored_contact = contact_service.get_contact(test_contact.id)
    assert restored_contact is not None
    assert restored_contact.id == test_contact.id


def test_hard_delete_contact(db: Session, test_contact):
    """Test hard deleting a contact."""
    contact_service = ContactService(db)

    # Hard delete the contact
    success = contact_service.hard_delete_contact(test_contact.id)
    assert success is True

    # Verify it's permanently deleted
    deleted_contact = contact_service.get_contact(test_contact.id)
    assert deleted_contact is None


def test_get_deleted_contacts(db: Session, test_contact):
    """Test getting soft-deleted contacts."""
    contact_service = ContactService(db)

    # Delete the contact
    contact_service.delete_contact(test_contact.id)

    # Get deleted contacts
    deleted_contacts = contact_service.get_deleted_contacts()
    assert len(deleted_contacts) >= 1
    assert any(c.id == test_contact.id for c in deleted_contacts)


def test_get_deleted_contact(db: Session, test_contact):
    """Test getting a specific soft-deleted contact."""
    contact_service = ContactService(db)

    # Delete the contact
    contact_service.delete_contact(test_contact.id)

    # Get the deleted contact
    deleted_contact = contact_service.get_deleted_contact(test_contact.id)
    assert deleted_contact is not None
    assert deleted_contact.id == test_contact.id


def test_get_contacts_deleted_after(db: Session, test_contact):
    """Test getting contacts deleted after a specific date."""
    contact_service = ContactService(db)

    # Delete the contact
    contact_service.delete_contact(test_contact.id)

    # Get contacts deleted after a past date
    past_date = datetime(2020, 1, 1)
    deleted_contacts = contact_service.get_contacts_deleted_after(past_date)
    assert len(deleted_contacts) >= 1
    assert any(c.id == test_contact.id for c in deleted_contacts)


def test_search_text(db: Session, test_contact):
    """Test searching contacts by text across multiple fields."""
    contact_service = ContactService(db)

    # Search by first name
    results = contact_service.search_text(test_contact.first_name)
    assert len(results) >= 1
    assert any(c.id == test_contact.id for c in results)

    # Search by last name
    results = contact_service.search_text(test_contact.last_name)
    assert len(results) >= 1
    assert any(c.id == test_contact.id for c in results)

    # Search by company
    if test_contact.company:
        results = contact_service.search_text(test_contact.company)
        assert len(results) >= 1
        assert any(c.id == test_contact.id for c in results)

    # Search by email
    if test_contact.email:
        results = contact_service.search_text(test_contact.email)
        assert len(results) >= 1
        assert any(c.id == test_contact.id for c in results)

    # Search with no match
    results = contact_service.search_text("nonexistentsearchterm12345")
    assert len(results) == 0


def test_search_text_with_pagination(db: Session, test_contact):
    """Test searching contacts by text with pagination."""
    contact_service = ContactService(db)

    # Search with skip and limit
    results = contact_service.search_text(test_contact.first_name, skip=0, limit=10)
    assert isinstance(results, list)
    assert len(results) <= 10


def test_search_text_case_insensitive(db: Session, test_contact):
    """Test that text search is case-insensitive."""
    contact_service = ContactService(db)

    # Search with lowercase
    results_lower = contact_service.search_text(test_contact.first_name.lower())

    # Search with uppercase
    results_upper = contact_service.search_text(test_contact.first_name.upper())

    # Both should return the same results
    assert len(results_lower) == len(results_upper)
    assert any(c.id == test_contact.id for c in results_lower)
    assert any(c.id == test_contact.id for c in results_upper)

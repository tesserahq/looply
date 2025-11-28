import pytest
from uuid import uuid4
from datetime import datetime
from sqlalchemy.orm import Session
from app.schemas.contact_list import ContactListCreate, ContactListUpdate
from app.services.contact_list_service import ContactListService


@pytest.fixture
def sample_contact_list_data(faker, test_user):
    return {
        "name": faker.company(),
        "description": faker.text(max_nb_chars=200),
        "created_by_id": test_user.id,
    }


@pytest.fixture
def minimal_contact_list_data(faker, test_user):
    return {
        "name": faker.company(),
        "created_by_id": test_user.id,
    }


def test_create_contact_list(db, sample_contact_list_data):
    """Test creating a contact list with full data."""
    contact_list_create = ContactListCreate(**sample_contact_list_data)
    contact_list = ContactListService(db).create_contact_list(contact_list_create)

    # Assertions
    assert contact_list.id is not None
    assert contact_list.name == sample_contact_list_data["name"]
    assert contact_list.description == sample_contact_list_data["description"]
    assert contact_list.created_by_id == sample_contact_list_data["created_by_id"]
    assert contact_list.created_at is not None
    assert contact_list.updated_at is not None


def test_create_contact_list_minimal_data(db, minimal_contact_list_data):
    """Test creating a contact list with minimal required data."""
    contact_list_create = ContactListCreate(**minimal_contact_list_data)
    contact_list = ContactListService(db).create_contact_list(contact_list_create)

    # Assertions
    assert contact_list.id is not None
    assert contact_list.name == minimal_contact_list_data["name"]
    assert contact_list.description is None
    assert contact_list.created_by_id == minimal_contact_list_data["created_by_id"]
    assert contact_list.created_at is not None
    assert contact_list.updated_at is not None


def test_get_contact_list(db, test_contact_list):
    """Test retrieving a contact list by ID."""
    retrieved_contact_list = ContactListService(db).get_contact_list(
        test_contact_list.id
    )

    # Assertions
    assert retrieved_contact_list is not None
    assert retrieved_contact_list.id == test_contact_list.id
    assert retrieved_contact_list.name == test_contact_list.name
    assert retrieved_contact_list.description == test_contact_list.description


def test_get_contact_lists(db, test_contact_list):
    """Test retrieving all contact lists with pagination."""
    contact_lists = ContactListService(db).get_contact_lists()

    # Assertions
    assert len(contact_lists) >= 1
    assert any(c.id == test_contact_list.id for c in contact_lists)


def test_get_contact_lists_by_creator(db, test_contact_list):
    """Test retrieving contact lists by creator."""
    contact_lists = ContactListService(db).get_contact_lists_by_creator(
        test_contact_list.created_by_id
    )

    # Assertions
    assert len(contact_lists) >= 1
    assert any(c.id == test_contact_list.id for c in contact_lists)
    assert all(
        c.created_by_id == test_contact_list.created_by_id for c in contact_lists
    )


def test_update_contact_list(db, test_contact_list):
    """Test updating a contact list."""
    update_data = {
        "name": "Updated List Name",
        "description": "Updated description for the contact list",
    }
    contact_list_update = ContactListUpdate(**update_data)

    # Update contact list
    updated_contact_list = ContactListService(db).update_contact_list(
        test_contact_list.id, contact_list_update
    )

    # Assertions
    assert updated_contact_list is not None
    assert updated_contact_list.id == test_contact_list.id
    assert updated_contact_list.name == update_data["name"]
    assert updated_contact_list.description == update_data["description"]
    # Verify other fields remain unchanged
    assert updated_contact_list.created_by_id == test_contact_list.created_by_id
    assert updated_contact_list.created_at == test_contact_list.created_at


def test_update_contact_list_partial(db, test_contact_list):
    """Test updating a contact list with partial data."""
    update_data = {"name": "Only Name Updated"}
    contact_list_update = ContactListUpdate(**update_data)

    # Update contact list
    updated_contact_list = ContactListService(db).update_contact_list(
        test_contact_list.id, contact_list_update
    )

    # Assertions
    assert updated_contact_list is not None
    assert updated_contact_list.name == update_data["name"]
    # Verify other fields remain unchanged
    assert updated_contact_list.description == test_contact_list.description
    assert updated_contact_list.created_by_id == test_contact_list.created_by_id


def test_delete_contact_list(db, test_contact_list):
    """Test soft deleting a contact list."""
    contact_list_service = ContactListService(db)

    # Delete contact list
    success = contact_list_service.delete_contact_list(test_contact_list.id)

    # Assertions
    assert success is True
    deleted_contact_list = contact_list_service.get_contact_list(test_contact_list.id)
    assert deleted_contact_list is None


def test_contact_list_not_found_cases(db):
    """Test various not found cases."""
    contact_list_service = ContactListService(db)
    non_existent_id = uuid4()

    # Get non-existent contact list
    assert contact_list_service.get_contact_list(non_existent_id) is None

    # Update non-existent contact list
    update_data = {"name": "Updated"}
    contact_list_update = ContactListUpdate(**update_data)
    assert (
        contact_list_service.update_contact_list(non_existent_id, contact_list_update)
        is None
    )

    # Delete non-existent contact list
    assert contact_list_service.delete_contact_list(non_existent_id) is False


def test_search_contact_lists_with_filters(db, test_contact_list):
    """Test searching contact lists with dynamic filters."""
    # Search using ilike filter on name
    filters = {
        "name": {"operator": "ilike", "value": f"%{test_contact_list.name[:5]}%"}
    }
    results = ContactListService(db).search(filters)

    assert isinstance(results, list)
    assert any(contact_list.id == test_contact_list.id for contact_list in results)

    # Search using exact match
    filters = {"name": test_contact_list.name}
    results = ContactListService(db).search(filters)

    assert len(results) == 1
    assert results[0].id == test_contact_list.id

    # Search with no match
    filters = {"name": {"operator": "==", "value": "nonexistent list"}}
    results = ContactListService(db).search(filters)

    assert len(results) == 0


def test_search_contact_lists_by_description(db, test_contact_list):
    """Test searching contact lists by description."""
    if test_contact_list.description:
        filters = {
            "description": {
                "operator": "ilike",
                "value": f"%{test_contact_list.description[:10]}%",
            }
        }
        results = ContactListService(db).search(filters)

        assert isinstance(results, list)
        assert any(contact_list.id == test_contact_list.id for contact_list in results)


def test_get_contact_lists_query(db, test_contact_list):
    """Test getting a query object for contact lists."""
    contact_list_service = ContactListService(db)
    query = contact_list_service.get_contact_lists_query()

    # Verify it's a query object
    assert query is not None

    # Verify it can be used to get results
    results = query.all()
    assert len(results) >= 1
    assert any(c.id == test_contact_list.id for c in results)


def test_restore_contact_list(db, test_contact_list):
    """Test restoring a soft-deleted contact list."""
    contact_list_service = ContactListService(db)

    # First delete the contact list
    contact_list_service.delete_contact_list(test_contact_list.id)
    assert contact_list_service.get_contact_list(test_contact_list.id) is None

    # Then restore it
    success = contact_list_service.restore_contact_list(test_contact_list.id)
    assert success is True

    # Verify it's restored
    restored_contact_list = contact_list_service.get_contact_list(test_contact_list.id)
    assert restored_contact_list is not None
    assert restored_contact_list.id == test_contact_list.id


def test_hard_delete_contact_list(db, test_contact_list):
    """Test hard deleting a contact list."""
    contact_list_service = ContactListService(db)

    # Hard delete the contact list
    success = contact_list_service.hard_delete_contact_list(test_contact_list.id)
    assert success is True

    # Verify it's permanently deleted
    deleted_contact_list = contact_list_service.get_contact_list(test_contact_list.id)
    assert deleted_contact_list is None


def test_get_deleted_contact_lists(db, test_contact_list):
    """Test getting soft-deleted contact lists."""
    contact_list_service = ContactListService(db)

    # Delete the contact list
    contact_list_service.delete_contact_list(test_contact_list.id)

    # Get deleted contact lists
    deleted_contact_lists = contact_list_service.get_deleted_contact_lists()
    assert len(deleted_contact_lists) >= 1
    assert any(c.id == test_contact_list.id for c in deleted_contact_lists)


def test_get_deleted_contact_list(db, test_contact_list):
    """Test getting a specific soft-deleted contact list."""
    contact_list_service = ContactListService(db)

    # Delete the contact list
    contact_list_service.delete_contact_list(test_contact_list.id)

    # Get the deleted contact list
    deleted_contact_list = contact_list_service.get_deleted_contact_list(
        test_contact_list.id
    )
    assert deleted_contact_list is not None
    assert deleted_contact_list.id == test_contact_list.id


def test_get_contact_lists_deleted_after(db, test_contact_list):
    """Test getting contact lists deleted after a specific date."""
    contact_list_service = ContactListService(db)

    # Delete the contact list
    contact_list_service.delete_contact_list(test_contact_list.id)

    # Get contact lists deleted after a past date
    past_date = datetime(2020, 1, 1)
    deleted_contact_lists = contact_list_service.get_contact_lists_deleted_after(
        past_date
    )
    assert len(deleted_contact_lists) >= 1
    assert any(c.id == test_contact_list.id for c in deleted_contact_lists)


def test_create_multiple_contact_lists(db, test_user, faker):
    """Test creating multiple contact lists for the same user."""
    contact_list_service = ContactListService(db)

    # Create multiple contact lists
    contact_lists = []
    for i in range(5):
        contact_list_data = {
            "name": f"{faker.company()} {i}",
            "description": faker.text(max_nb_chars=100),
            "created_by_id": test_user.id,
        }
        contact_list_create = ContactListCreate(**contact_list_data)
        contact_list = contact_list_service.create_contact_list(contact_list_create)
        contact_lists.append(contact_list)

    # Verify all were created
    assert len(contact_lists) == 5

    # Retrieve all contact lists by creator
    retrieved_contact_lists = contact_list_service.get_contact_lists_by_creator(
        test_user.id
    )
    assert len(retrieved_contact_lists) >= 5


def test_contact_list_pagination(db, test_contact_list, faker, test_user):
    """Test pagination of contact lists."""
    contact_list_service = ContactListService(db)

    # Create multiple contact lists
    for i in range(10):
        contact_list_data = {
            "name": f"{faker.company()} {i}",
            "description": faker.text(max_nb_chars=100),
            "created_by_id": test_user.id,
        }
        contact_list_create = ContactListCreate(**contact_list_data)
        contact_list_service.create_contact_list(contact_list_create)

    # Test pagination with skip and limit
    first_batch = contact_list_service.get_contact_lists(skip=0, limit=5)
    second_batch = contact_list_service.get_contact_lists(skip=5, limit=5)

    assert len(first_batch) == 5
    assert len(second_batch) == 5
    assert first_batch[0].id != second_batch[0].id

import pytest
from app.models.contact_list import ContactList


@pytest.fixture(scope="function")
def test_contact_list(db, faker, test_user):
    """Create a test contact list for use in tests."""
    contact_list_data = {
        "name": faker.company(),
        "description": faker.text(max_nb_chars=200),
        "created_by_id": test_user.id,
    }

    contact_list = ContactList(**contact_list_data)
    db.add(contact_list)
    db.commit()
    db.refresh(contact_list)

    return contact_list


@pytest.fixture(scope="function")
def setup_contact_list(db, faker, setup_user):
    """Create a test contact list for use in tests."""
    contact_list_data = {
        "name": faker.company(),
        "description": faker.text(max_nb_chars=200),
        "created_by_id": setup_user.id,
    }

    contact_list = ContactList(**contact_list_data)
    db.add(contact_list)
    db.commit()
    db.refresh(contact_list)

    return contact_list


@pytest.fixture(scope="function")
def setup_another_contact_list(db, faker, setup_another_user):
    """Create another test contact list for use in tests."""
    contact_list_data = {
        "name": faker.company(),
        "description": faker.text(max_nb_chars=200),
        "created_by_id": setup_another_user.id,
    }

    contact_list = ContactList(**contact_list_data)
    db.add(contact_list)
    db.commit()
    db.refresh(contact_list)

    return contact_list


@pytest.fixture(scope="function")
def contact_list_with_minimal_data(db, faker, test_user):
    """Create a contact list with minimal required data."""
    contact_list_data = {
        "name": faker.company(),
        "created_by_id": test_user.id,
    }

    contact_list = ContactList(**contact_list_data)
    db.add(contact_list)
    db.commit()
    db.refresh(contact_list)

    return contact_list

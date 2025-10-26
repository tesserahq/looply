import pytest
from app.models.contact import Contact


@pytest.fixture(scope="function")
def test_contact(db, faker, test_user):
    """Create a test contact for use in tests."""
    contact_data = {
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

    contact = Contact(**contact_data)
    db.add(contact)
    db.commit()
    db.refresh(contact)

    return contact


@pytest.fixture(scope="function")
def setup_contact(db, faker, setup_user):
    """Create a test contact for use in tests."""
    contact_data = {
        "first_name": faker.first_name(),
        "last_name": faker.last_name(),
        "company": faker.company(),
        "job": faker.job(),
        "contact_type": "personal",
        "phone_type": "mobile",
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
        "created_by_id": setup_user.id,
    }

    contact = Contact(**contact_data)
    db.add(contact)
    db.commit()
    db.refresh(contact)

    return contact


@pytest.fixture(scope="function")
def setup_another_contact(db, faker, setup_another_user):
    """Create another test contact for use in tests."""
    contact_data = {
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
        "created_by_id": setup_another_user.id,
    }

    contact = Contact(**contact_data)
    db.add(contact)
    db.commit()
    db.refresh(contact)

    return contact


@pytest.fixture(scope="function")
def inactive_contact(db, faker, test_user):
    """Create an inactive test contact for use in tests."""
    contact_data = {
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
        "is_active": False,
        "created_by_id": test_user.id,
    }

    contact = Contact(**contact_data)
    db.add(contact)
    db.commit()
    db.refresh(contact)

    return contact


@pytest.fixture(scope="function")
def contact_with_minimal_data(db, faker, test_user):
    """Create a contact with minimal required data."""
    contact_data = {
        "contact_type": "personal",
        "phone_type": "mobile",
        "created_by_id": test_user.id,
    }

    contact = Contact(**contact_data)
    db.add(contact)
    db.commit()
    db.refresh(contact)

    return contact

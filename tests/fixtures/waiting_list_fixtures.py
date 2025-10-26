import pytest
from app.models.waiting_list import WaitingList


@pytest.fixture(scope="function")
def test_waiting_list(db, faker, test_user):
    """Create a test waiting list for use in tests."""
    waiting_list_data = {
        "name": faker.company(),
        "description": faker.text(max_nb_chars=200),
        "created_by_id": test_user.id,
    }

    waiting_list = WaitingList(**waiting_list_data)
    db.add(waiting_list)
    db.commit()
    db.refresh(waiting_list)

    return waiting_list


@pytest.fixture(scope="function")
def setup_waiting_list(db, faker, setup_user):
    """Create a test waiting list for use in tests."""
    waiting_list_data = {
        "name": faker.company(),
        "description": faker.text(max_nb_chars=200),
        "created_by_id": setup_user.id,
    }

    waiting_list = WaitingList(**waiting_list_data)
    db.add(waiting_list)
    db.commit()
    db.refresh(waiting_list)

    return waiting_list


@pytest.fixture(scope="function")
def waiting_list_with_minimal_data(db, faker, test_user):
    """Create a waiting list with minimal required data."""
    waiting_list_data = {
        "name": faker.company(),
        "created_by_id": test_user.id,
    }

    waiting_list = WaitingList(**waiting_list_data)
    db.add(waiting_list)
    db.commit()
    db.refresh(waiting_list)

    return waiting_list

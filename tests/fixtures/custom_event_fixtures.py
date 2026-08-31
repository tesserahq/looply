import pytest
from app.models.custom_event import CustomEvent


@pytest.fixture(scope="function")
def test_custom_event(db, faker, test_contact):
    """Create a custom event for test_contact."""
    event = CustomEvent(
        contact_id=test_contact.id,
        name="com.mylinden.person.created",
        occurred_at=faker.date_time(),
        properties={"person": {"id": str(faker.uuid4())}},
        raw_envelope={"event_type": "com.mylinden.person.created"},
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    return event

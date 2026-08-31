from datetime import datetime, timezone

from app.repositories.custom_event_repository import CustomEventRepository


def test_create_event(db, test_contact):
    repository = CustomEventRepository(db)
    event = repository.create_event(
        contact_id=test_contact.id,
        name="com.mylinden.person.created",
        occurred_at=datetime.now(timezone.utc),
        properties={"person": {"id": "abc"}},
        raw_envelope={"event_type": "com.mylinden.person.created", "id": "raw-id"},
    )

    assert event.id is not None
    assert event.contact_id == test_contact.id
    assert event.name == "com.mylinden.person.created"
    assert event.properties == {"person": {"id": "abc"}}
    assert event.raw_envelope["id"] == "raw-id"


def test_create_event_is_append_only(db, test_contact):
    """A second event for the same contact/name is its own row, not an overwrite."""
    repository = CustomEventRepository(db)
    repository.create_event(
        contact_id=test_contact.id,
        name="com.mylinden.person.created",
        occurred_at=datetime.now(timezone.utc),
        properties={},
        raw_envelope={},
    )
    repository.create_event(
        contact_id=test_contact.id,
        name="com.mylinden.person.created",
        occurred_at=datetime.now(timezone.utc),
        properties={},
        raw_envelope={},
    )

    events = repository.list_events_for_contact(test_contact.id)
    assert len(events) == 2


def test_list_events_for_contact_filters_by_name(db, test_contact):
    repository = CustomEventRepository(db)
    repository.create_event(
        contact_id=test_contact.id,
        name="com.mylinden.person.created",
        occurred_at=datetime.now(timezone.utc),
        properties={},
        raw_envelope={},
    )
    repository.create_event(
        contact_id=test_contact.id,
        name="com.mylinden.pet.created",
        occurred_at=datetime.now(timezone.utc),
        properties={},
        raw_envelope={},
    )

    events = repository.list_events_for_contact(
        test_contact.id, name="com.mylinden.pet.created"
    )
    assert len(events) == 1
    assert events[0].name == "com.mylinden.pet.created"


def test_list_events_for_contact_empty(db, test_contact):
    repository = CustomEventRepository(db)
    assert repository.list_events_for_contact(test_contact.id) == []


def test_get_events_query_no_filters(db, test_contact):
    repository = CustomEventRepository(db)
    repository.create_event(
        contact_id=test_contact.id,
        name="com.mylinden.person.created",
        occurred_at=datetime.now(timezone.utc),
        properties={},
        raw_envelope={},
    )

    results = repository.get_events_query().all()
    assert len(results) == 1


def test_get_events_query_filters_by_name_and_contact_id(
    db, test_contact, setup_contact
):
    repository = CustomEventRepository(db)
    repository.create_event(
        contact_id=test_contact.id,
        name="com.mylinden.person.created",
        occurred_at=datetime.now(timezone.utc),
        properties={},
        raw_envelope={},
    )
    repository.create_event(
        contact_id=setup_contact.id,
        name="com.mylinden.pet.created",
        occurred_at=datetime.now(timezone.utc),
        properties={},
        raw_envelope={},
    )

    by_name = repository.get_events_query(name="com.mylinden.pet.created").all()
    assert len(by_name) == 1
    assert by_name[0].contact_id == setup_contact.id

    by_contact = repository.get_events_query(contact_id=test_contact.id).all()
    assert len(by_contact) == 1
    assert by_contact[0].contact_id == test_contact.id

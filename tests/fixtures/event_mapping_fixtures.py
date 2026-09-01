import pytest
from app.models.event_mapping import EventMapping


@pytest.fixture(scope="function")
def test_event_mapping(db, test_user):
    """Register "com.mylinden.person.created" with no identity configured yet -
    the minimal EventMapping, mirroring the old test_tracked_event_type
    fixture's role."""
    event_mapping = EventMapping(
        event_type="com.mylinden.person.created",
        created_by_id=test_user.id,
    )
    db.add(event_mapping)
    db.commit()
    db.refresh(event_mapping)

    return event_mapping


@pytest.fixture(scope="function")
def test_identity_event_mapping(db, test_user):
    """Register "com.mylinden.person.updated" with its identity configured as
    event_data.person.id -> Contact.external_id - the minimum every event_type
    needs to resolve/auto-create a contact at all."""
    event_mapping = EventMapping(
        event_type="com.mylinden.person.updated",
        identity_target_field="external_id",
        identity_source_path="person.id",
        created_by_id=test_user.id,
    )
    db.add(event_mapping)
    db.commit()
    db.refresh(event_mapping)

    return event_mapping

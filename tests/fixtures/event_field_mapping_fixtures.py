import pytest
from app.models.event_field_mapping import EventFieldMapping


@pytest.fixture(scope="function")
def test_event_field_mapping(db, test_number_field_definition, test_user):
    """Create an event-to-field mapping targeting test_number_field_definition."""
    mapping = EventFieldMapping(
        event_type="com.mylinden.person.created",
        source_path="account.family_member_count",
        field_definition_id=test_number_field_definition.id,
        created_by_id=test_user.id,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)

    return mapping

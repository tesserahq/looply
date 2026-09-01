import pytest
from app.models.event_field_mapping import EventFieldMapping


@pytest.fixture(scope="function")
def test_event_field_mapping(db, test_event_mapping, test_number_field_definition, test_user):
    """Create an attribute mapping under test_event_mapping targeting
    test_number_field_definition."""
    mapping = EventFieldMapping(
        event_mapping_id=test_event_mapping.id,
        source_path="account.family_member_count",
        target_type="custom_field",
        field_definition_id=test_number_field_definition.id,
        created_by_id=test_user.id,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)

    return mapping

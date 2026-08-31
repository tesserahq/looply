import pytest
from app.models.event_field_mapping import EventFieldMapping


@pytest.fixture(scope="function")
def test_event_field_mapping(db, test_number_field_definition, test_user):
    """Create an event-to-field mapping targeting test_number_field_definition."""
    mapping = EventFieldMapping(
        event_type="com.mylinden.person.created",
        source_path="account.family_member_count",
        target_type="custom_field",
        field_definition_id=test_number_field_definition.id,
        created_by_id=test_user.id,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)

    return mapping


@pytest.fixture(scope="function")
def test_identity_key_mapping(db, test_user):
    """Register "com.mylinden.person.updated"'s identity key as
    event_data.person.id -> Contact.external_id - the minimum every event_type
    needs to resolve/auto-create a contact at all."""
    mapping = EventFieldMapping(
        event_type="com.mylinden.person.updated",
        source_path="person.id",
        target_type="contact_field",
        target_field="external_id",
        is_identity_key=True,
        created_by_id=test_user.id,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)

    return mapping

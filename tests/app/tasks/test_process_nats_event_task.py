"""Tests for the NATS event ingestion task - called directly with a plain dict the
way orcha's process_nats_event_task tests do, no live NATS connection needed.
"""

from app.repositories.contact_custom_field_value_repository import (
    ContactCustomFieldValueRepository,
)
from app.repositories.contact_repository import ContactRepository
from app.repositories.custom_event_repository import CustomEventRepository
from app.repositories.event_field_mapping_repository import (
    EventFieldMappingRepository,
)
from app.schemas.event_field_mapping import EventFieldMappingCreate
from app.tasks.process_nats_event_task import _process_nats_event


def _envelope(**overrides):
    envelope = {
        "source": "/linden",
        "spec_version": "1.0",
        "event_type": "com.mylinden.person.updated",
        "event_data": {"person": {"id": "p1"}},
        "time": "2026-08-29T01:54:07.442732",
        "tags": ["person_id:p1"],
        "labels": {"person_id": "p1"},
        "user": {
            "id": "user-external-id",
            "email": "harry@example.com",
            "first_name": "Harry",
            "last_name": "Potter",
        },
        "id": "cc618d7f-envelope-id",
    }
    envelope.update(overrides)
    return envelope


def test_untracked_event_type_is_dropped(db):
    """No TrackedEventType is registered for "com.mylinden.person.updated" here -
    the event must be dropped before any Contact resolution is attempted."""
    envelope = _envelope()

    event_id = _process_nats_event(db, envelope)

    assert event_id is None
    assert ContactRepository(db).get_contact_by_external_id("user-external-id") is None


def test_known_external_id_records_event_without_modifying_identity(
    db, test_contact, test_tracked_event_type
):
    test_contact.external_id = "user-external-id"
    original_email = test_contact.email
    db.commit()

    envelope = _envelope(
        user={
            "id": "user-external-id",
            "email": "someone-else@example.com",
            "first_name": "Different",
            "last_name": "Name",
        }
    )

    event_id = _process_nats_event(db, envelope)

    assert event_id is not None
    events = CustomEventRepository(db).list_events_for_contact(test_contact.id)
    assert len(events) == 1
    assert events[0].name == "com.mylinden.person.updated"
    assert events[0].properties == {"person": {"id": "p1"}}

    db.refresh(test_contact)
    assert test_contact.email == original_email
    assert test_contact.first_name != "Different"


def test_unknown_external_id_auto_creates_contact(db, test_tracked_event_type):
    envelope = _envelope()

    event_id = _process_nats_event(db, envelope)

    assert event_id is not None
    contact = ContactRepository(db).get_contact_by_external_id("user-external-id")
    assert contact is not None
    assert contact.email == "harry@example.com"
    assert contact.first_name == "Harry"
    assert contact.last_name == "Potter"
    assert contact.created_by_id is None

    events = CustomEventRepository(db).list_events_for_contact(contact.id)
    assert len(events) == 1


def test_raw_envelope_stored_verbatim(db, test_tracked_event_type):
    envelope = _envelope()

    _process_nats_event(db, envelope)

    contact = ContactRepository(db).get_contact_by_external_id("user-external-id")
    events = CustomEventRepository(db).list_events_for_contact(contact.id)
    assert events[0].raw_envelope == envelope


def test_missing_user_id_is_dropped(db, test_tracked_event_type):
    envelope = _envelope(user={})

    event_id = _process_nats_event(db, envelope)

    assert event_id is None


def test_matching_mapping_writes_custom_field(
    db, test_tracked_event_type, test_number_field_definition, test_user
):
    EventFieldMappingRepository(db).create_mapping(
        EventFieldMappingCreate(
            event_type="com.mylinden.person.updated",
            source_path="person.account.family_member_count",
            field_definition_id=test_number_field_definition.id,
            created_by_id=test_user.id,
        )
    )
    envelope = _envelope(
        event_data={"person": {"id": "p1", "account": {"family_member_count": 3}}}
    )

    _process_nats_event(db, envelope)

    contact = ContactRepository(db).get_contact_by_external_id("user-external-id")
    value = ContactCustomFieldValueRepository(db).get_value_by_field_name(
        contact.id, test_number_field_definition.name
    )
    assert value is not None
    assert value.value == 3
    assert value.set_by_user_id is None


def test_mapping_with_missing_path_is_skipped(
    db, test_tracked_event_type, test_number_field_definition, test_user
):
    EventFieldMappingRepository(db).create_mapping(
        EventFieldMappingCreate(
            event_type="com.mylinden.person.updated",
            source_path="person.does.not.exist",
            field_definition_id=test_number_field_definition.id,
            created_by_id=test_user.id,
        )
    )
    envelope = _envelope(event_data={"person": {"id": "p1"}})

    event_id = _process_nats_event(db, envelope)

    assert event_id is not None
    contact = ContactRepository(db).get_contact_by_external_id("user-external-id")
    assert (
        ContactCustomFieldValueRepository(db).get_value_by_field_name(
            contact.id, test_number_field_definition.name
        )
        is None
    )


def test_mapping_with_type_mismatch_is_skipped_but_event_still_recorded(
    db, test_tracked_event_type, test_number_field_definition, test_user
):
    """test_number_field_definition is NUMBER - a string value must not be written,
    but that failure must not roll back the CustomEvent."""
    EventFieldMappingRepository(db).create_mapping(
        EventFieldMappingCreate(
            event_type="com.mylinden.person.updated",
            source_path="person.name",
            field_definition_id=test_number_field_definition.id,
            created_by_id=test_user.id,
        )
    )
    envelope = _envelope(event_data={"person": {"id": "p1", "name": "Harry"}})

    event_id = _process_nats_event(db, envelope)

    assert event_id is not None
    contact = ContactRepository(db).get_contact_by_external_id("user-external-id")
    assert (
        ContactCustomFieldValueRepository(db).get_value_by_field_name(
            contact.id, test_number_field_definition.name
        )
        is None
    )
    events = CustomEventRepository(db).list_events_for_contact(contact.id)
    assert len(events) == 1


def test_no_matching_mapping_is_a_noop(db, test_tracked_event_type):
    envelope = _envelope()

    event_id = _process_nats_event(db, envelope)

    assert event_id is not None

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
    """Shaped like the real production envelope this PRD's bug report was based
    on: "user"/"person"/"account" nested under event_data, no top-level "user"."""
    envelope = {
        "source": "/linden",
        "spec_version": "1.0",
        "event_type": "com.mylinden.person.updated",
        "event_data": {
            "person": {
                "id": "person-external-id",
                "email": "harry@example.com",
                "first_name": "Harry",
                "last_name": "Potter",
            },
            "user": {"id": "acting-user-id"},
        },
        "time": "2026-08-29T01:54:07.442732",
        "tags": ["person_id:person-external-id"],
        "labels": {"person_id": "person-external-id"},
        "user_id": "acting-user-id",
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
    assert (
        ContactRepository(db).get_contact_by_external_id("person-external-id")
        is None
    )


def test_no_identity_key_mapping_is_dropped(db, test_tracked_event_type):
    """Tracked, but nobody has configured an identity-key mapping for this
    event_type yet - must be dropped, same fail-safe behavior as an unresolved
    path, not a crash."""
    envelope = _envelope()

    event_id = _process_nats_event(db, envelope)

    assert event_id is None


def test_known_external_id_records_event_without_modifying_identity(
    db, test_contact, test_tracked_event_type, test_identity_key_mapping
):
    test_contact.external_id = "person-external-id"
    original_email = test_contact.email
    db.commit()

    envelope = _envelope(
        event_data={
            "person": {
                "id": "person-external-id",
                "email": "someone-else@example.com",
                "first_name": "Different",
                "last_name": "Name",
            }
        }
    )

    event_id = _process_nats_event(db, envelope)

    assert event_id is not None
    events = CustomEventRepository(db).list_events_for_contact(test_contact.id)
    assert len(events) == 1
    assert events[0].name == "com.mylinden.person.updated"

    db.refresh(test_contact)
    assert test_contact.email == original_email
    assert test_contact.first_name != "Different"


def test_unknown_external_id_auto_creates_contact_from_person_not_user(
    db, test_tracked_event_type, test_identity_key_mapping
):
    """The identity key targets event_data.person.id, not event_data.user.id -
    regression test for the "10 family members collapse onto one user" bug this
    PRD fixes."""
    envelope = _envelope()

    event_id = _process_nats_event(db, envelope)

    assert event_id is not None
    contact = ContactRepository(db).get_contact_by_external_id("person-external-id")
    assert contact is not None
    assert contact.created_by_id is None

    events = CustomEventRepository(db).list_events_for_contact(contact.id)
    assert len(events) == 1


def test_auto_created_contact_stamped_with_tracked_event_type_source(
    db, test_user, test_identity_key_mapping
):
    from app.models.tracked_event_type import TrackedEventType

    tracked = TrackedEventType(
        event_type="com.mylinden.person.updated",
        source="linden",
        created_by_id=test_user.id,
    )
    db.add(tracked)
    db.commit()

    envelope = _envelope()
    _process_nats_event(db, envelope)

    contact = ContactRepository(db).get_contact_by_external_id("person-external-id")
    assert contact.source == "linden"


def test_email_identity_key_resolves_by_email(db, test_user):
    """A different event_type configured to key off email instead of
    external_id resolves/creates via Contact.email."""
    from app.models.tracked_event_type import TrackedEventType
    from app.models.event_field_mapping import EventFieldMapping

    db.add(
        TrackedEventType(
            event_type="com.mylinden.pet.created",
            created_by_id=test_user.id,
        )
    )
    db.add(
        EventFieldMapping(
            event_type="com.mylinden.pet.created",
            source_path="owner.email",
            target_type="contact_field",
            target_field="email",
            is_identity_key=True,
            created_by_id=test_user.id,
        )
    )
    db.commit()

    envelope = _envelope(
        event_type="com.mylinden.pet.created",
        event_data={"owner": {"email": "owner@example.com"}},
    )

    event_id = _process_nats_event(db, envelope)

    assert event_id is not None
    contact = ContactRepository(db).get_contact_by_email("owner@example.com")
    assert contact is not None


def test_raw_envelope_stored_verbatim(
    db, test_tracked_event_type, test_identity_key_mapping
):
    envelope = _envelope()

    _process_nats_event(db, envelope)

    contact = ContactRepository(db).get_contact_by_external_id("person-external-id")
    events = CustomEventRepository(db).list_events_for_contact(contact.id)
    assert events[0].raw_envelope == envelope


def test_identity_key_path_not_resolving_is_dropped(
    db, test_tracked_event_type, test_identity_key_mapping
):
    envelope = _envelope(event_data={"person": {}})

    event_id = _process_nats_event(db, envelope)

    assert event_id is None


def test_contact_field_mapping_populates_contact_attribute(
    db, test_tracked_event_type, test_user
):
    from app.models.event_field_mapping import EventFieldMapping

    db.add(
        EventFieldMapping(
            event_type="com.mylinden.person.updated",
            source_path="person.id",
            target_type="contact_field",
            target_field="external_id",
            is_identity_key=True,
            created_by_id=test_user.id,
        )
    )
    db.add(
        EventFieldMapping(
            event_type="com.mylinden.person.updated",
            source_path="person.first_name",
            target_type="contact_field",
            target_field="first_name",
            created_by_id=test_user.id,
        )
    )
    db.commit()

    envelope = _envelope(
        event_data={"person": {"id": "person-external-id", "first_name": "Harry"}}
    )

    _process_nats_event(db, envelope)

    contact = ContactRepository(db).get_contact_by_external_id("person-external-id")
    assert contact.first_name == "Harry"


def test_matching_custom_field_mapping_writes_custom_field(
    db,
    test_tracked_event_type,
    test_identity_key_mapping,
    test_number_field_definition,
    test_user,
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
        event_data={
            "person": {
                "id": "person-external-id",
                "account": {"family_member_count": 3},
            }
        }
    )

    _process_nats_event(db, envelope)

    contact = ContactRepository(db).get_contact_by_external_id("person-external-id")
    value = ContactCustomFieldValueRepository(db).get_value_by_field_name(
        contact.id, test_number_field_definition.name
    )
    assert value is not None
    assert value.value == 3
    assert value.set_by_user_id is None


def test_custom_field_mapping_with_missing_path_is_skipped(
    db,
    test_tracked_event_type,
    test_identity_key_mapping,
    test_number_field_definition,
    test_user,
):
    EventFieldMappingRepository(db).create_mapping(
        EventFieldMappingCreate(
            event_type="com.mylinden.person.updated",
            source_path="person.does.not.exist",
            field_definition_id=test_number_field_definition.id,
            created_by_id=test_user.id,
        )
    )
    envelope = _envelope(event_data={"person": {"id": "person-external-id"}})

    event_id = _process_nats_event(db, envelope)

    assert event_id is not None
    contact = ContactRepository(db).get_contact_by_external_id("person-external-id")
    assert (
        ContactCustomFieldValueRepository(db).get_value_by_field_name(
            contact.id, test_number_field_definition.name
        )
        is None
    )


def test_custom_field_mapping_with_type_mismatch_is_skipped_but_event_still_recorded(
    db,
    test_tracked_event_type,
    test_identity_key_mapping,
    test_number_field_definition,
    test_user,
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
    envelope = _envelope(
        event_data={"person": {"id": "person-external-id", "name": "Harry"}}
    )

    event_id = _process_nats_event(db, envelope)

    assert event_id is not None
    contact = ContactRepository(db).get_contact_by_external_id("person-external-id")
    assert (
        ContactCustomFieldValueRepository(db).get_value_by_field_name(
            contact.id, test_number_field_definition.name
        )
        is None
    )
    events = CustomEventRepository(db).list_events_for_contact(contact.id)
    assert len(events) == 1


def test_no_matching_mapping_is_a_noop(
    db, test_tracked_event_type, test_identity_key_mapping
):
    envelope = _envelope()

    event_id = _process_nats_event(db, envelope)

    assert event_id is not None

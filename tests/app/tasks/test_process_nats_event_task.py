"""Tests for the NATS event ingestion task - called directly with a plain dict the
way orcha's process_nats_event_task tests do, no live NATS connection needed.
"""

from app.models.event_field_mapping import EventFieldMapping
from app.models.event_mapping import EventMapping
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
    """No EventMapping is registered for "com.mylinden.person.updated" here -
    the event must be dropped before any Contact resolution is attempted."""
    envelope = _envelope()

    event_id = _process_nats_event(db, envelope)

    assert event_id is None
    assert (
        ContactRepository(db).get_contact_by_external_id("person-external-id") is None
    )


def test_no_identity_configured_is_dropped(db, test_event_mapping, test_user):
    """test_event_mapping registers "com.mylinden.person.created", not
    "com.mylinden.person.updated" - register the right event_type with no
    identity configured to hit this case."""
    unidentified = EventMapping(
        event_type="com.mylinden.person.updated", created_by_id=test_user.id
    )
    db.add(unidentified)
    db.commit()

    envelope = _envelope()

    event_id = _process_nats_event(db, envelope)

    assert event_id is None


def test_known_external_id_records_event_without_modifying_identity(
    db, test_contact, test_identity_event_mapping
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
    db, test_identity_event_mapping
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


def test_auto_created_contact_stamped_with_event_mapping_source(db, test_user):
    event_mapping = EventMapping(
        event_type="com.mylinden.person.updated",
        source="linden",
        identity_target_field="external_id",
        identity_source_path="person.id",
        created_by_id=test_user.id,
    )
    db.add(event_mapping)
    db.commit()

    envelope = _envelope()
    _process_nats_event(db, envelope)

    contact = ContactRepository(db).get_contact_by_external_id("person-external-id")
    assert contact.source == "linden"


def test_auto_created_contact_stamped_with_default_status_and_tags(db, test_user):
    event_mapping = EventMapping(
        event_type="com.mylinden.person.updated",
        identity_target_field="external_id",
        identity_source_path="person.id",
        default_status="pending",
        default_tags=["lead", "linden"],
        created_by_id=test_user.id,
    )
    db.add(event_mapping)
    db.commit()

    envelope = _envelope()
    _process_nats_event(db, envelope)

    contact = ContactRepository(db).get_contact_by_external_id("person-external-id")
    assert contact.status == "pending"
    assert sorted(contact.tags) == ["lead", "linden"]


def test_known_contact_status_and_tags_not_overwritten_by_defaults(
    db, test_contact, test_identity_event_mapping
):
    """An event resolving to an already-existing contact must not have its
    status/tags overwritten by the mapping's default_status/default_tags -
    same no-clobber guarantee as other contact fields."""
    test_contact.external_id = "person-external-id"
    test_contact.status = "active"
    db.commit()

    test_identity_event_mapping.default_status = "inactive"
    test_identity_event_mapping.default_tags = ["should-not-apply"]
    db.commit()

    envelope = _envelope()
    _process_nats_event(db, envelope)

    db.refresh(test_contact)
    assert test_contact.status == "active"
    assert test_contact.tags == []


def test_email_identity_key_resolves_by_email(db, test_user):
    """A different event_type configured to key off email instead of
    external_id resolves/creates via Contact.email."""
    db.add(
        EventMapping(
            event_type="com.mylinden.pet.created",
            identity_target_field="email",
            identity_source_path="owner.email",
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


def test_raw_envelope_stored_verbatim(db, test_identity_event_mapping):
    envelope = _envelope()

    _process_nats_event(db, envelope)

    contact = ContactRepository(db).get_contact_by_external_id("person-external-id")
    events = CustomEventRepository(db).list_events_for_contact(contact.id)
    assert events[0].raw_envelope == envelope


def test_identity_path_not_resolving_is_dropped(db, test_identity_event_mapping):
    envelope = _envelope(event_data={"person": {}})

    event_id = _process_nats_event(db, envelope)

    assert event_id is None


def test_contact_field_mapping_populates_contact_attribute(
    db, test_identity_event_mapping, test_user
):
    db.add(
        EventFieldMapping(
            event_mapping_id=test_identity_event_mapping.id,
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
    test_identity_event_mapping,
    test_number_field_definition,
    test_user,
):
    EventFieldMappingRepository(db).create_mapping(
        EventFieldMappingCreate(
            event_mapping_id=test_identity_event_mapping.id,
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
    test_identity_event_mapping,
    test_number_field_definition,
    test_user,
):
    EventFieldMappingRepository(db).create_mapping(
        EventFieldMappingCreate(
            event_mapping_id=test_identity_event_mapping.id,
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
    test_identity_event_mapping,
    test_number_field_definition,
    test_user,
):
    """test_number_field_definition is NUMBER - a string value must not be written,
    but that failure must not roll back the CustomEvent."""
    EventFieldMappingRepository(db).create_mapping(
        EventFieldMappingCreate(
            event_mapping_id=test_identity_event_mapping.id,
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


def test_no_matching_mapping_is_a_noop(db, test_identity_event_mapping):
    envelope = _envelope()

    event_id = _process_nats_event(db, envelope)

    assert event_id is not None

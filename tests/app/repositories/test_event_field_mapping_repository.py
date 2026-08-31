from app.repositories.event_field_mapping_repository import (
    DuplicateIdentityKeyError,
    EventFieldMappingRepository,
    InvalidEventFieldMappingError,
)
from app.schemas.event_field_mapping import (
    EventFieldMappingCreate,
    EventFieldMappingTargetType,
)
import pytest


def test_create_mapping(db, test_custom_field_definition, test_user):
    repository = EventFieldMappingRepository(db)
    mapping = repository.create_mapping(
        EventFieldMappingCreate(
            event_type="com.mylinden.person.created",
            source_path="account.family_member_count",
            field_definition_id=test_custom_field_definition.id,
            created_by_id=test_user.id,
        )
    )

    assert mapping.id is not None
    assert mapping.field_name == test_custom_field_definition.name


def test_get_mappings_for_event_type(db, test_custom_field_definition, test_user):
    repository = EventFieldMappingRepository(db)
    repository.create_mapping(
        EventFieldMappingCreate(
            event_type="com.mylinden.person.created",
            source_path="a",
            field_definition_id=test_custom_field_definition.id,
            created_by_id=test_user.id,
        )
    )
    repository.create_mapping(
        EventFieldMappingCreate(
            event_type="com.mylinden.pet.created",
            source_path="b",
            field_definition_id=test_custom_field_definition.id,
            created_by_id=test_user.id,
        )
    )

    matches = repository.get_mappings_for_event_type("com.mylinden.person.created")
    assert len(matches) == 1
    assert matches[0].source_path == "a"


def test_get_mappings_for_event_type_no_match(db):
    assert (
        EventFieldMappingRepository(db).get_mappings_for_event_type("no.such.type")
        == []
    )


def test_delete_mapping_stops_it_matching(db, test_custom_field_definition, test_user):
    repository = EventFieldMappingRepository(db)
    mapping = repository.create_mapping(
        EventFieldMappingCreate(
            event_type="com.mylinden.person.created",
            source_path="a",
            field_definition_id=test_custom_field_definition.id,
            created_by_id=test_user.id,
        )
    )

    assert repository.delete_mapping(mapping.id) is True
    assert repository.get_mappings_for_event_type("com.mylinden.person.created") == []


def test_delete_mapping_not_found(db):
    from uuid import uuid4

    assert EventFieldMappingRepository(db).delete_mapping(uuid4()) is False


def test_create_contact_field_mapping(db, test_user):
    repository = EventFieldMappingRepository(db)
    mapping = repository.create_mapping(
        EventFieldMappingCreate(
            event_type="com.mylinden.person.updated",
            source_path="person.first_name",
            target_type=EventFieldMappingTargetType.CONTACT_FIELD,
            target_field="first_name",
            created_by_id=test_user.id,
        )
    )

    assert mapping.target_type == "contact_field"
    assert mapping.target_field == "first_name"
    assert mapping.field_definition_id is None
    assert mapping.field_name is None


def test_create_contact_field_mapping_unrecognized_target_field(db, test_user):
    repository = EventFieldMappingRepository(db)
    with pytest.raises(InvalidEventFieldMappingError):
        repository.create_mapping(
            EventFieldMappingCreate(
                event_type="com.mylinden.person.updated",
                source_path="person.something",
                target_type=EventFieldMappingTargetType.CONTACT_FIELD,
                target_field="not_a_real_column",
                created_by_id=test_user.id,
            )
        )


def test_create_identity_key_mapping(db, test_user):
    repository = EventFieldMappingRepository(db)
    mapping = repository.create_mapping(
        EventFieldMappingCreate(
            event_type="com.mylinden.person.updated",
            source_path="person.id",
            target_type=EventFieldMappingTargetType.CONTACT_FIELD,
            target_field="external_id",
            is_identity_key=True,
            created_by_id=test_user.id,
        )
    )

    assert mapping.is_identity_key is True


def test_create_identity_key_mapping_on_non_identity_field_rejected(db, test_user):
    repository = EventFieldMappingRepository(db)
    with pytest.raises(InvalidEventFieldMappingError):
        repository.create_mapping(
            EventFieldMappingCreate(
                event_type="com.mylinden.person.updated",
                source_path="person.first_name",
                target_type=EventFieldMappingTargetType.CONTACT_FIELD,
                target_field="first_name",
                is_identity_key=True,
                created_by_id=test_user.id,
            )
        )


def test_create_second_identity_key_mapping_for_same_event_type_rejected(
    db, test_user
):
    repository = EventFieldMappingRepository(db)
    repository.create_mapping(
        EventFieldMappingCreate(
            event_type="com.mylinden.person.updated",
            source_path="person.id",
            target_type=EventFieldMappingTargetType.CONTACT_FIELD,
            target_field="external_id",
            is_identity_key=True,
            created_by_id=test_user.id,
        )
    )

    with pytest.raises(DuplicateIdentityKeyError):
        repository.create_mapping(
            EventFieldMappingCreate(
                event_type="com.mylinden.person.updated",
                source_path="person.other_id",
                target_type=EventFieldMappingTargetType.CONTACT_FIELD,
                target_field="email",
                is_identity_key=True,
                created_by_id=test_user.id,
            )
        )


def test_identity_key_mapping_allowed_for_different_event_types(db, test_user):
    repository = EventFieldMappingRepository(db)
    repository.create_mapping(
        EventFieldMappingCreate(
            event_type="com.mylinden.person.updated",
            source_path="person.id",
            target_type=EventFieldMappingTargetType.CONTACT_FIELD,
            target_field="external_id",
            is_identity_key=True,
            created_by_id=test_user.id,
        )
    )

    second = repository.create_mapping(
        EventFieldMappingCreate(
            event_type="com.mylinden.pet.created",
            source_path="owner.id",
            target_type=EventFieldMappingTargetType.CONTACT_FIELD,
            target_field="external_id",
            is_identity_key=True,
            created_by_id=test_user.id,
        )
    )

    assert second.is_identity_key is True

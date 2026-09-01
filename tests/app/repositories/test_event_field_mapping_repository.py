from app.repositories.event_field_mapping_repository import (
    EventFieldMappingRepository,
    InvalidEventFieldMappingError,
)
from app.schemas.event_field_mapping import (
    EventFieldMappingCreate,
    EventFieldMappingTargetType,
)
import pytest


def test_create_mapping(db, test_event_mapping, test_custom_field_definition, test_user):
    repository = EventFieldMappingRepository(db)
    mapping = repository.create_mapping(
        EventFieldMappingCreate(
            event_mapping_id=test_event_mapping.id,
            source_path="account.family_member_count",
            field_definition_id=test_custom_field_definition.id,
            created_by_id=test_user.id,
        )
    )

    assert mapping.id is not None
    assert mapping.field_name == test_custom_field_definition.name


def test_get_mappings_for_event_mapping(
    db, test_event_mapping, test_custom_field_definition, test_user
):
    repository = EventFieldMappingRepository(db)
    repository.create_mapping(
        EventFieldMappingCreate(
            event_mapping_id=test_event_mapping.id,
            source_path="a",
            field_definition_id=test_custom_field_definition.id,
            created_by_id=test_user.id,
        )
    )

    from app.models.event_mapping import EventMapping

    other_event_mapping = EventMapping(
        event_type="com.mylinden.pet.created", created_by_id=test_user.id
    )
    db.add(other_event_mapping)
    db.commit()
    db.refresh(other_event_mapping)
    repository.create_mapping(
        EventFieldMappingCreate(
            event_mapping_id=other_event_mapping.id,
            source_path="b",
            field_definition_id=test_custom_field_definition.id,
            created_by_id=test_user.id,
        )
    )

    matches = repository.get_mappings_for_event_mapping(test_event_mapping.id)
    assert len(matches) == 1
    assert matches[0].source_path == "a"


def test_get_mappings_for_event_mapping_no_match(db, test_event_mapping):
    assert (
        EventFieldMappingRepository(db).get_mappings_for_event_mapping(
            test_event_mapping.id
        )
        == []
    )


def test_delete_mapping_stops_it_matching(
    db, test_event_mapping, test_custom_field_definition, test_user
):
    repository = EventFieldMappingRepository(db)
    mapping = repository.create_mapping(
        EventFieldMappingCreate(
            event_mapping_id=test_event_mapping.id,
            source_path="a",
            field_definition_id=test_custom_field_definition.id,
            created_by_id=test_user.id,
        )
    )

    assert repository.delete_mapping(mapping.id) is True
    assert repository.get_mappings_for_event_mapping(test_event_mapping.id) == []


def test_delete_mapping_not_found(db):
    from uuid import uuid4

    assert EventFieldMappingRepository(db).delete_mapping(uuid4()) is False


def test_create_contact_field_mapping(db, test_event_mapping, test_user):
    repository = EventFieldMappingRepository(db)
    mapping = repository.create_mapping(
        EventFieldMappingCreate(
            event_mapping_id=test_event_mapping.id,
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


def test_create_contact_field_mapping_unrecognized_target_field(
    db, test_event_mapping, test_user
):
    repository = EventFieldMappingRepository(db)
    with pytest.raises(InvalidEventFieldMappingError):
        repository.create_mapping(
            EventFieldMappingCreate(
                event_mapping_id=test_event_mapping.id,
                source_path="person.something",
                target_type=EventFieldMappingTargetType.CONTACT_FIELD,
                target_field="not_a_real_column",
                created_by_id=test_user.id,
            )
        )


def test_update_mapping_source_path(
    db, test_event_mapping, test_custom_field_definition, test_user
):
    repository = EventFieldMappingRepository(db)
    mapping = repository.create_mapping(
        EventFieldMappingCreate(
            event_mapping_id=test_event_mapping.id,
            source_path="a",
            field_definition_id=test_custom_field_definition.id,
            created_by_id=test_user.id,
        )
    )

    updated = repository.update_mapping(mapping.id, source_path="b")

    assert updated.source_path == "b"
    assert updated.field_definition_id == test_custom_field_definition.id


def test_update_mapping_switch_to_contact_field(
    db, test_event_mapping, test_custom_field_definition, test_user
):
    repository = EventFieldMappingRepository(db)
    mapping = repository.create_mapping(
        EventFieldMappingCreate(
            event_mapping_id=test_event_mapping.id,
            source_path="a",
            field_definition_id=test_custom_field_definition.id,
            created_by_id=test_user.id,
        )
    )

    updated = repository.update_mapping(
        mapping.id,
        target_type=EventFieldMappingTargetType.CONTACT_FIELD,
        target_field="city",
        clear_field_definition_id=True,
    )

    assert updated.target_type == "contact_field"
    assert updated.target_field == "city"
    assert updated.field_definition_id is None


def test_update_mapping_unrecognized_target_field_rejected(
    db, test_event_mapping, test_user
):
    repository = EventFieldMappingRepository(db)
    mapping = repository.create_mapping(
        EventFieldMappingCreate(
            event_mapping_id=test_event_mapping.id,
            source_path="a",
            target_type=EventFieldMappingTargetType.CONTACT_FIELD,
            target_field="city",
            created_by_id=test_user.id,
        )
    )

    with pytest.raises(InvalidEventFieldMappingError):
        repository.update_mapping(mapping.id, target_field="not_a_real_column")


def test_update_mapping_not_found(db):
    from uuid import uuid4

    assert (
        EventFieldMappingRepository(db).update_mapping(uuid4(), source_path="x")
        is None
    )

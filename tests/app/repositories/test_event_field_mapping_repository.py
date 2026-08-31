from app.repositories.event_field_mapping_repository import (
    EventFieldMappingRepository,
)
from app.schemas.event_field_mapping import EventFieldMappingCreate


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

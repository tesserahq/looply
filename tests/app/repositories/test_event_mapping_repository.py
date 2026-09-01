import pytest

from app.repositories.event_field_mapping_repository import EventFieldMappingRepository
from app.repositories.event_mapping_repository import (
    EventMappingConflictError,
    EventMappingRepository,
    InvalidEventMappingError,
)
from app.schemas.event_field_mapping import EventFieldMappingCreate
from app.schemas.event_mapping import EventMappingCreate, EventMappingUpdateRequest


def test_create_event_mapping(db, test_user):
    repository = EventMappingRepository(db)
    event_mapping = repository.create_event_mapping(
        EventMappingCreate(
            event_type="com.mylinden.person.created", created_by_id=test_user.id
        )
    )

    assert event_mapping.id is not None
    assert event_mapping.event_type == "com.mylinden.person.created"
    assert event_mapping.identity_target_field is None


def test_create_event_mapping_with_identity(db, test_user):
    repository = EventMappingRepository(db)
    event_mapping = repository.create_event_mapping(
        EventMappingCreate(
            event_type="com.mylinden.person.updated",
            identity_target_field="external_id",
            identity_source_path="person.id",
            created_by_id=test_user.id,
        )
    )

    assert event_mapping.identity_target_field == "external_id"
    assert event_mapping.identity_source_path == "person.id"


def test_create_event_mapping_invalid_identity_target_field(db, test_user):
    repository = EventMappingRepository(db)
    with pytest.raises(InvalidEventMappingError):
        repository.create_event_mapping(
            EventMappingCreate(
                event_type="com.mylinden.person.updated",
                identity_target_field="first_name",
                identity_source_path="person.first_name",
                created_by_id=test_user.id,
            )
        )


def test_create_duplicate_event_type_conflict(db, test_user):
    repository = EventMappingRepository(db)
    repository.create_event_mapping(
        EventMappingCreate(
            event_type="com.mylinden.person.created", created_by_id=test_user.id
        )
    )

    with pytest.raises(EventMappingConflictError):
        repository.create_event_mapping(
            EventMappingCreate(
                event_type="com.mylinden.person.created", created_by_id=test_user.id
            )
        )


def test_get_by_event_type(db, test_event_mapping):
    repository = EventMappingRepository(db)
    found = repository.get_by_event_type(test_event_mapping.event_type)

    assert found is not None
    assert found.id == test_event_mapping.id


def test_get_by_event_type_not_registered(db):
    assert EventMappingRepository(db).get_by_event_type("no.such.type") is None


def test_update_event_mapping_identity(db, test_event_mapping):
    repository = EventMappingRepository(db)
    updated = repository.update_event_mapping(
        test_event_mapping.id,
        EventMappingUpdateRequest(
            identity_target_field="email", identity_source_path="person.email"
        ),
    )

    assert updated.identity_target_field == "email"
    assert updated.identity_source_path == "person.email"


def test_update_event_mapping_invalid_identity_target_field(db, test_event_mapping):
    repository = EventMappingRepository(db)
    with pytest.raises(InvalidEventMappingError):
        repository.update_event_mapping(
            test_event_mapping.id,
            EventMappingUpdateRequest(
                identity_target_field="city", identity_source_path="person.city"
            ),
        )


def test_update_event_mapping_not_found(db):
    from uuid import uuid4

    assert (
        EventMappingRepository(db).update_event_mapping(
            uuid4(), EventMappingUpdateRequest(source="linden")
        )
        is None
    )


def test_delete_event_mapping_stops_it_matching(db, test_event_mapping):
    repository = EventMappingRepository(db)

    assert repository.delete_event_mapping(test_event_mapping.id) is True
    assert repository.get_by_event_type(test_event_mapping.event_type) is None


def test_delete_event_mapping_not_found(db):
    from uuid import uuid4

    assert EventMappingRepository(db).delete_event_mapping(uuid4()) is False


def test_delete_event_mapping_cascades_to_field_mappings(
    db, test_event_mapping, test_custom_field_definition, test_user
):
    field_repo = EventFieldMappingRepository(db)
    mapping = field_repo.create_mapping(
        EventFieldMappingCreate(
            event_mapping_id=test_event_mapping.id,
            source_path="account.family_member_count",
            field_definition_id=test_custom_field_definition.id,
            created_by_id=test_user.id,
        )
    )

    EventMappingRepository(db).delete_event_mapping(test_event_mapping.id)

    assert field_repo.get_mapping(mapping.id) is None


def test_delete_then_recreate_same_event_type(db, test_user):
    repository = EventMappingRepository(db)
    event_mapping = repository.create_event_mapping(
        EventMappingCreate(
            event_type="com.mylinden.person.created", created_by_id=test_user.id
        )
    )
    repository.delete_event_mapping(event_mapping.id)

    recreated = repository.create_event_mapping(
        EventMappingCreate(
            event_type="com.mylinden.person.created", created_by_id=test_user.id
        )
    )
    assert recreated.id != event_mapping.id

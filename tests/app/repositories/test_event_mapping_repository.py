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


def test_create_event_mapping_with_default_status_and_tags(db, test_user):
    repository = EventMappingRepository(db)
    event_mapping = repository.create_event_mapping(
        EventMappingCreate(
            event_type="com.mylinden.person.created",
            default_status="pending",
            default_tags=["lead", "linden"],
            created_by_id=test_user.id,
        )
    )

    assert event_mapping.default_status == "pending"
    assert event_mapping.default_tags == ["lead", "linden"]


def test_update_event_mapping_default_status_and_tags(db, test_event_mapping):
    repository = EventMappingRepository(db)
    updated = repository.update_event_mapping(
        test_event_mapping.id,
        EventMappingUpdateRequest(default_status="inactive", default_tags=["vip"]),
    )

    assert updated.default_status == "inactive"
    assert updated.default_tags == ["vip"]


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


def test_create_event_mapping_defaults_to_active(db, test_user):
    repository = EventMappingRepository(db)
    event_mapping = repository.create_event_mapping(
        EventMappingCreate(
            event_type="com.mylinden.person.created", created_by_id=test_user.id
        )
    )

    assert event_mapping.is_active is True


def test_disable_and_reenable_event_mapping(db, test_event_mapping):
    repository = EventMappingRepository(db)

    disabled = repository.update_event_mapping(
        test_event_mapping.id, EventMappingUpdateRequest(is_active=False)
    )
    assert disabled.is_active is False

    reenabled = repository.update_event_mapping(
        test_event_mapping.id, EventMappingUpdateRequest(is_active=True)
    )
    assert reenabled.is_active is True


def test_clone_event_mapping_from_disabled_source_is_active(
    db, test_event_mapping, test_user
):
    repository = EventMappingRepository(db)
    repository.update_event_mapping(
        test_event_mapping.id, EventMappingUpdateRequest(is_active=False)
    )

    clone = repository.clone_event_mapping(
        test_event_mapping, "com.mylinden.person.deleted", test_user.id
    )

    assert clone.is_active is True


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


def test_clone_event_mapping(db, test_identity_event_mapping, test_user):
    repository = EventMappingRepository(db)
    clone = repository.clone_event_mapping(
        test_identity_event_mapping, "com.mylinden.person.deleted", test_user.id
    )

    assert clone.id != test_identity_event_mapping.id
    assert clone.event_type == "com.mylinden.person.deleted"
    assert clone.identity_target_field == "external_id"
    assert clone.identity_source_path == "person.id"
    assert clone.created_by_id == test_user.id


def test_clone_event_mapping_deep_copies_field_mappings(
    db, test_event_mapping, test_event_field_mapping, test_user
):
    repository = EventMappingRepository(db)
    clone = repository.clone_event_mapping(
        test_event_mapping, "com.mylinden.person.deleted", test_user.id
    )

    field_repo = EventFieldMappingRepository(db)
    cloned_fields = field_repo.get_mappings_for_event_mapping(clone.id)

    assert len(cloned_fields) == 1
    cloned_field = cloned_fields[0]
    assert cloned_field.id != test_event_field_mapping.id
    assert cloned_field.source_path == test_event_field_mapping.source_path
    assert cloned_field.target_type == test_event_field_mapping.target_type
    assert (
        cloned_field.field_definition_id == test_event_field_mapping.field_definition_id
    )
    assert cloned_field.created_by_id == test_user.id

    # editing the clone's field mapping leaves the source untouched
    field_repo.update_mapping(cloned_field.id, source_path="changed.path")
    assert field_repo.get_mapping(test_event_field_mapping.id).source_path == (
        test_event_field_mapping.source_path
    )


def test_clone_event_mapping_duplicate_conflict(db, test_event_mapping, test_user):
    repository = EventMappingRepository(db)
    with pytest.raises(EventMappingConflictError):
        repository.clone_event_mapping(
            test_event_mapping, test_event_mapping.event_type, test_user.id
        )


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

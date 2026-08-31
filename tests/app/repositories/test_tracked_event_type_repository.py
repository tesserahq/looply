import pytest

from app.repositories.tracked_event_type_repository import (
    TrackedEventTypeConflictError,
    TrackedEventTypeRepository,
)
from app.schemas.tracked_event_type import TrackedEventTypeCreate


def test_create_tracked_event_type(db, test_user):
    repository = TrackedEventTypeRepository(db)
    tracked = repository.create_tracked_event_type(
        TrackedEventTypeCreate(
            event_type="com.mylinden.person.created", created_by_id=test_user.id
        )
    )

    assert tracked.id is not None
    assert tracked.event_type == "com.mylinden.person.created"


def test_create_duplicate_event_type_conflict(db, test_user):
    repository = TrackedEventTypeRepository(db)
    repository.create_tracked_event_type(
        TrackedEventTypeCreate(
            event_type="com.mylinden.person.created", created_by_id=test_user.id
        )
    )

    with pytest.raises(TrackedEventTypeConflictError):
        repository.create_tracked_event_type(
            TrackedEventTypeCreate(
                event_type="com.mylinden.person.created", created_by_id=test_user.id
            )
        )


def test_get_by_event_type(db, test_tracked_event_type):
    repository = TrackedEventTypeRepository(db)
    found = repository.get_by_event_type(test_tracked_event_type.event_type)

    assert found is not None
    assert found.id == test_tracked_event_type.id


def test_get_by_event_type_not_tracked(db):
    assert TrackedEventTypeRepository(db).get_by_event_type("no.such.type") is None


def test_delete_tracked_event_type_stops_it_matching(db, test_tracked_event_type):
    repository = TrackedEventTypeRepository(db)

    assert repository.delete_tracked_event_type(test_tracked_event_type.id) is True
    assert repository.get_by_event_type(test_tracked_event_type.event_type) is None


def test_delete_tracked_event_type_not_found(db):
    from uuid import uuid4

    assert TrackedEventTypeRepository(db).delete_tracked_event_type(uuid4()) is False


def test_delete_then_recreate_same_event_type(db, test_user):
    repository = TrackedEventTypeRepository(db)
    tracked = repository.create_tracked_event_type(
        TrackedEventTypeCreate(
            event_type="com.mylinden.person.created", created_by_id=test_user.id
        )
    )
    repository.delete_tracked_event_type(tracked.id)

    recreated = repository.create_tracked_event_type(
        TrackedEventTypeCreate(
            event_type="com.mylinden.person.created", created_by_id=test_user.id
        )
    )
    assert recreated.id != tracked.id

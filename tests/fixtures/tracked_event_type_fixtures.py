import pytest
from app.models.tracked_event_type import TrackedEventType


@pytest.fixture(scope="function")
def test_tracked_event_type(db, test_user):
    """Register "com.mylinden.person.updated" as a tracked event type."""
    tracked = TrackedEventType(
        event_type="com.mylinden.person.updated",
        created_by_id=test_user.id,
    )
    db.add(tracked)
    db.commit()
    db.refresh(tracked)

    return tracked

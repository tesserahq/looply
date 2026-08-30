import pytest
from app.models.segment import Segment


@pytest.fixture(scope="function")
def test_segment(db, faker, test_user, test_contact_list):
    """Create a segment matching everyone in test_contact_list."""
    segment = Segment(
        name=faker.catch_phrase(),
        rule={
            "root": {
                "type": "list_membership",
                "list_id": str(test_contact_list.id),
                "op": "in",
            }
        },
        created_by_id=test_user.id,
    )
    db.add(segment)
    db.commit()
    db.refresh(segment)

    return segment

from uuid import uuid4

import pytest

from app.constants.campaign import CampaignStatus
from app.models.campaign import Campaign
from app.repositories.segment_repository import (
    SegmentNameConflictError,
    SegmentRepository,
)
from app.repositories.segment_resolver import SegmentResolutionError
from app.schemas.segment import SegmentCreate, SegmentUpdate
from app.schemas.segment_rule import SegmentRuleCreate


def _list_membership_rule(list_id) -> SegmentRuleCreate:
    return SegmentRuleCreate.model_validate(
        {"root": {"type": "list_membership", "list_id": str(list_id), "op": "in"}}
    )


def test_create_segment(db, faker, test_user, test_contact_list):
    repository = SegmentRepository(db)
    segment = repository.create_segment(
        SegmentCreate(
            name=faker.catch_phrase(),
            rule=_list_membership_rule(test_contact_list.id),
            created_by_id=test_user.id,
        )
    )

    assert segment.id is not None
    assert segment.rule["root"]["list_id"] == str(test_contact_list.id)


def test_create_segment_duplicate_name_conflict(
    db, faker, test_user, test_contact_list
):
    repository = SegmentRepository(db)
    name = faker.catch_phrase()
    repository.create_segment(
        SegmentCreate(
            name=name,
            rule=_list_membership_rule(test_contact_list.id),
            created_by_id=test_user.id,
        )
    )

    with pytest.raises(SegmentNameConflictError):
        repository.create_segment(
            SegmentCreate(
                name=name,
                rule=_list_membership_rule(test_contact_list.id),
                created_by_id=test_user.id,
            )
        )


def test_create_segment_rejects_dangling_campaign_reference(db, faker, test_user):
    repository = SegmentRepository(db)
    rule = SegmentRuleCreate.model_validate(
        {
            "root": {
                "type": "campaign_activity",
                "campaign_id": str(uuid4()),
                "event": "opened",
                "op": "has_not",
            }
        }
    )

    with pytest.raises(SegmentResolutionError):
        repository.create_segment(
            SegmentCreate(
                name=faker.catch_phrase(), rule=rule, created_by_id=test_user.id
            )
        )


def test_get_segment(db, test_segment):
    repository = SegmentRepository(db)
    segment = repository.get_segment(test_segment.id)

    assert segment is not None
    assert segment.id == test_segment.id


def test_get_segment_not_found(db):
    repository = SegmentRepository(db)
    assert repository.get_segment(uuid4()) is None


def test_update_segment_name(db, test_segment, faker):
    repository = SegmentRepository(db)
    new_name = faker.catch_phrase()
    updated = repository.update_segment(test_segment.id, SegmentUpdate(name=new_name))

    assert updated.name == new_name


def test_update_segment_rule(db, test_segment, test_contact_list, faker, test_user):
    from app.models.contact_list import ContactList

    other_list = ContactList(name=faker.company(), created_by_id=test_user.id)
    db.add(other_list)
    db.commit()
    db.refresh(other_list)

    repository = SegmentRepository(db)
    updated = repository.update_segment(
        test_segment.id, SegmentUpdate(rule=_list_membership_rule(other_list.id))
    )

    assert updated.rule["root"]["list_id"] == str(other_list.id)


def test_update_segment_not_found(db, faker):
    repository = SegmentRepository(db)
    assert (
        repository.update_segment(uuid4(), SegmentUpdate(name=faker.catch_phrase()))
        is None
    )


def test_delete_segment(db, test_segment):
    repository = SegmentRepository(db)
    assert repository.delete_segment(test_segment.id) is True
    assert repository.get_segment(test_segment.id) is None


def test_preview_count(db, test_segment, test_contact, test_contact_list):
    from app.repositories.contact_list_repository import ContactListRepository

    ContactListRepository(db).add_contact_to_list(test_contact_list.id, test_contact.id)

    repository = SegmentRepository(db)
    assert repository.preview_count(test_segment) == 1


def test_preview_count_raises_for_dangling_campaign_reference(
    db, faker, test_user, test_segment
):
    draft = Campaign(
        name=faker.catch_phrase(),
        status=CampaignStatus.DRAFT.value,
        segment_id=test_segment.id,
        created_by_id=test_user.id,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)

    repository = SegmentRepository(db)
    rule = SegmentRuleCreate.model_validate(
        {
            "root": {
                "type": "campaign_activity",
                "campaign_id": str(draft.id),
                "event": "opened",
                "op": "has",
            }
        }
    )
    # Bypass create_segment's own validation to simulate a segment that
    # became dangling after the campaign was reverted from completed.
    test_segment.rule = rule.model_dump(mode="json")
    db.commit()

    with pytest.raises(SegmentResolutionError):
        repository.preview_count(test_segment)

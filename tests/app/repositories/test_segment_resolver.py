"""Tests for the segment rule resolver - the module the PRD calls out as the
highest-value one to get right, since every later phase and the send flow
depend on its correctness. Exercises a range of rule trees (single
condition, AND, OR, nested groups, has/has_not, in/not_in) against seeded
Contact/ContactListMember/CampaignRecipient fixtures, asserting exactly
which contacts resolve.
"""

from uuid import uuid4

import pytest

from app.constants.campaign import CampaignStatus
from app.models.campaign import Campaign
from app.models.campaign_recipient import CampaignRecipient
from app.models.contact import Contact
from app.models.contact_list import ContactList
from app.repositories.contact_list_repository import ContactListRepository
from app.repositories.segment_resolver import (
    SegmentResolutionError,
    resolve_contacts_query,
    resolve_count,
    validate_campaign_references,
)
from app.schemas.segment_rule import SegmentRuleCreate


def _contact(db, faker, test_user, **overrides):
    defaults = dict(
        first_name=faker.first_name(),
        last_name=faker.last_name(),
        email=faker.unique.email(),
        contact_type="business",
        phone_type="work",
        is_active=True,
        created_by_id=test_user.id,
    )
    defaults.update(overrides)
    contact = Contact(**defaults)
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def _completed_campaign(db, faker, test_user, test_segment):
    campaign = Campaign(
        name=faker.catch_phrase(),
        status=CampaignStatus.COMPLETED.value,
        segment_id=test_segment.id,
        batch_id=faker.uuid4(),
        created_by_id=test_user.id,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


def _root(rule: dict):
    return SegmentRuleCreate.model_validate({"root": rule}).root


def test_list_membership_in(db, faker, test_user, test_contact_list, test_contact):
    ContactListRepository(db).add_contact_to_list(test_contact_list.id, test_contact.id)
    outside = _contact(db, faker, test_user)

    root = _root(
        {"type": "list_membership", "list_id": str(test_contact_list.id), "op": "in"}
    )
    resolved_ids = {c.id for c in resolve_contacts_query(db, root).all()}

    assert test_contact.id in resolved_ids
    assert outside.id not in resolved_ids


def test_list_membership_not_in(db, faker, test_user, test_contact_list, test_contact):
    ContactListRepository(db).add_contact_to_list(test_contact_list.id, test_contact.id)
    outside = _contact(db, faker, test_user)

    root = _root(
        {"type": "list_membership", "list_id": str(test_contact_list.id), "op": "not_in"}
    )
    resolved_ids = {c.id for c in resolve_contacts_query(db, root).all()}

    assert test_contact.id not in resolved_ids
    assert outside.id in resolved_ids


def test_rule_tree_with_zero_list_membership_conditions_resolves_whole_contact_base(
    db, faker, test_user, test_contact_list, test_segment, test_contact
):
    """A rule tree with no list_membership condition at all - only
    campaign_activity - must resolve across the entire contact base, not
    just contacts in some particular list. See "Out of Scope" in the PRD:
    this is intentionally unguarded.
    """
    campaign = _completed_campaign(db, faker, test_user, test_segment)
    # test_contact is in test_contact_list; a second contact is in a
    # different list entirely. Both were sent the campaign but didn't open
    # it, so both must satisfy has_not - proving the resolution isn't scoped
    # to any one list.
    other_list = ContactList(name=faker.company(), created_by_id=test_user.id)
    db.add(other_list)
    db.commit()
    db.refresh(other_list)
    other_list_contact = _contact(db, faker, test_user)
    ContactListRepository(db).add_contact_to_list(test_contact_list.id, test_contact.id)
    ContactListRepository(db).add_contact_to_list(other_list.id, other_list_contact.id)
    db.add(CampaignRecipient(campaign_id=campaign.id, contact_id=test_contact.id))
    db.add(CampaignRecipient(campaign_id=campaign.id, contact_id=other_list_contact.id))
    # This contact was sent and opened it, so it must be excluded.
    opener = _contact(db, faker, test_user)
    db.add(
        CampaignRecipient(
            campaign_id=campaign.id, contact_id=opener.id, opened_at=faker.date_time()
        )
    )
    db.commit()

    root = _root(
        {
            "type": "campaign_activity",
            "campaign_id": str(campaign.id),
            "event": "opened",
            "op": "has_not",
        }
    )
    resolved_ids = {c.id for c in resolve_contacts_query(db, root).all()}

    assert test_contact.id in resolved_ids
    assert other_list_contact.id in resolved_ids
    assert opener.id not in resolved_ids


def test_campaign_activity_has(db, faker, test_user, test_segment, test_contact):
    campaign = _completed_campaign(db, faker, test_user, test_segment)
    db.add(
        CampaignRecipient(
            campaign_id=campaign.id, contact_id=test_contact.id, opened_at=faker.date_time()
        )
    )
    db.commit()
    never_sent = _contact(db, faker, test_user)

    root = _root(
        {
            "type": "campaign_activity",
            "campaign_id": str(campaign.id),
            "event": "opened",
            "op": "has",
        }
    )
    resolved_ids = {c.id for c in resolve_contacts_query(db, root).all()}

    assert test_contact.id in resolved_ids
    assert never_sent.id not in resolved_ids


def test_campaign_activity_has_not_excludes_never_sent(
    db, faker, test_user, test_segment, test_contact
):
    campaign = _completed_campaign(db, faker, test_user, test_segment)
    # Sent but did not open.
    db.add(CampaignRecipient(campaign_id=campaign.id, contact_id=test_contact.id))
    db.commit()
    never_sent = _contact(db, faker, test_user)

    root = _root(
        {
            "type": "campaign_activity",
            "campaign_id": str(campaign.id),
            "event": "opened",
            "op": "has_not",
        }
    )
    resolved_ids = {c.id for c in resolve_contacts_query(db, root).all()}

    assert test_contact.id in resolved_ids
    assert never_sent.id not in resolved_ids


def test_campaign_activity_has_not_excludes_openers(
    db, faker, test_user, test_segment, test_contact
):
    campaign = _completed_campaign(db, faker, test_user, test_segment)
    db.add(
        CampaignRecipient(
            campaign_id=campaign.id, contact_id=test_contact.id, opened_at=faker.date_time()
        )
    )
    db.commit()

    root = _root(
        {
            "type": "campaign_activity",
            "campaign_id": str(campaign.id),
            "event": "opened",
            "op": "has_not",
        }
    )
    resolved_ids = {c.id for c in resolve_contacts_query(db, root).all()}

    assert test_contact.id not in resolved_ids


def test_and_group(db, faker, test_user, test_contact_list, test_segment, test_contact):
    ContactListRepository(db).add_contact_to_list(test_contact_list.id, test_contact.id)
    campaign = _completed_campaign(db, faker, test_user, test_segment)
    db.add(
        CampaignRecipient(
            campaign_id=campaign.id, contact_id=test_contact.id, clicked_at=faker.date_time()
        )
    )
    db.commit()

    in_list_only = _contact(db, faker, test_user)
    ContactListRepository(db).add_contact_to_list(test_contact_list.id, in_list_only.id)

    root = _root(
        {
            "op": "and",
            "conditions": [
                {"type": "list_membership", "list_id": str(test_contact_list.id), "op": "in"},
                {
                    "type": "campaign_activity",
                    "campaign_id": str(campaign.id),
                    "event": "clicked",
                    "op": "has",
                },
            ],
        }
    )
    resolved_ids = {c.id for c in resolve_contacts_query(db, root).all()}

    assert test_contact.id in resolved_ids
    assert in_list_only.id not in resolved_ids


def test_or_group(db, faker, test_user, test_contact_list, test_contact):
    ContactListRepository(db).add_contact_to_list(test_contact_list.id, test_contact.id)
    other_list = ContactList(name=faker.company(), created_by_id=test_user.id)
    db.add(other_list)
    db.commit()
    db.refresh(other_list)
    other_contact = _contact(db, faker, test_user)
    ContactListRepository(db).add_contact_to_list(other_list.id, other_contact.id)
    neither = _contact(db, faker, test_user)

    root = _root(
        {
            "op": "or",
            "conditions": [
                {"type": "list_membership", "list_id": str(test_contact_list.id), "op": "in"},
                {"type": "list_membership", "list_id": str(other_list.id), "op": "in"},
            ],
        }
    )
    resolved_ids = {c.id for c in resolve_contacts_query(db, root).all()}

    assert test_contact.id in resolved_ids
    assert other_contact.id in resolved_ids
    assert neither.id not in resolved_ids


def test_nested_groups(db, faker, test_user, test_contact_list, test_contact):
    """(A or B) and not Newsletter - depth-2 nesting."""
    ContactListRepository(db).add_contact_to_list(test_contact_list.id, test_contact.id)
    newsletter = ContactList(name=faker.company(), created_by_id=test_user.id)
    db.add(newsletter)
    db.commit()
    db.refresh(newsletter)

    also_newsletter = _contact(db, faker, test_user)
    ContactListRepository(db).add_contact_to_list(test_contact_list.id, also_newsletter.id)
    ContactListRepository(db).add_contact_to_list(newsletter.id, also_newsletter.id)

    root = _root(
        {
            "op": "and",
            "conditions": [
                {
                    "op": "or",
                    "conditions": [
                        {
                            "type": "list_membership",
                            "list_id": str(test_contact_list.id),
                            "op": "in",
                        },
                    ],
                },
                {"type": "list_membership", "list_id": str(newsletter.id), "op": "not_in"},
            ],
        }
    )
    resolved_ids = {c.id for c in resolve_contacts_query(db, root).all()}

    assert test_contact.id in resolved_ids
    assert also_newsletter.id not in resolved_ids


def test_resolve_count_matches_resolve_contacts_length(
    db, faker, test_user, test_contact_list, test_contact
):
    ContactListRepository(db).add_contact_to_list(test_contact_list.id, test_contact.id)
    _contact(db, faker, test_user)  # outside the list

    root = _root(
        {"type": "list_membership", "list_id": str(test_contact_list.id), "op": "in"}
    )
    count = resolve_count(db, root)
    contacts = resolve_contacts_query(db, root).all()

    assert count == len(contacts)


def test_campaign_activity_rejects_nonexistent_campaign(db):
    root = _root(
        {
            "type": "campaign_activity",
            "campaign_id": str(uuid4()),
            "event": "opened",
            "op": "has_not",
        }
    )
    with pytest.raises(SegmentResolutionError):
        resolve_count(db, root)


def test_campaign_activity_rejects_non_completed_campaign(
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

    root = _root(
        {
            "type": "campaign_activity",
            "campaign_id": str(draft.id),
            "event": "opened",
            "op": "has",
        }
    )
    with pytest.raises(SegmentResolutionError):
        validate_campaign_references(db, root)

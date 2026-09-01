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
from app.repositories.contact_custom_field_value_repository import (
    ContactCustomFieldValueRepository,
)
from app.repositories.segment_resolver import (
    SegmentResolutionError,
    resolve_contacts_query,
    resolve_count,
    validate_campaign_references,
    validate_custom_field_references,
)
from app.schemas.segment_rule import SegmentRuleCreate


def _contact(db, faker, test_user, **overrides):
    defaults = dict(
        first_name=faker.first_name(),
        last_name=faker.last_name(),
        email=faker.unique.email(),
        contact_type="business",
        phone_type="work",
        status="active",
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
        {
            "type": "list_membership",
            "list_id": str(test_contact_list.id),
            "op": "not_in",
        }
    )
    resolved_ids = {c.id for c in resolve_contacts_query(db, root).all()}

    assert test_contact.id not in resolved_ids
    assert outside.id in resolved_ids


def test_tags_in_matches_any_of_selected_tags(db, faker, test_user, test_contact):
    from app.repositories.tag_repository import TagRepository

    tags = TagRepository(db).set_contact_tags(test_contact.id, ["vip"], test_user.id)
    other_tag = TagRepository(db).create_tag("lead", test_user.id)
    outside = _contact(db, faker, test_user)

    root = _root(
        {
            "type": "tags",
            "tag_ids": [str(tags[0].id), str(other_tag.id)],
            "op": "in",
        }
    )
    resolved_ids = {c.id for c in resolve_contacts_query(db, root).all()}

    assert test_contact.id in resolved_ids
    assert outside.id not in resolved_ids


def test_tags_not_in_excludes_contacts_with_any_selected_tag(
    db, faker, test_user, test_contact
):
    from app.repositories.tag_repository import TagRepository

    tags = TagRepository(db).set_contact_tags(test_contact.id, ["vip"], test_user.id)
    outside = _contact(db, faker, test_user)

    root = _root({"type": "tags", "tag_ids": [str(tags[0].id)], "op": "not_in"})
    resolved_ids = {c.id for c in resolve_contacts_query(db, root).all()}

    assert test_contact.id not in resolved_ids
    assert outside.id in resolved_ids


def test_tags_condition_referencing_deleted_tag_matches_nobody(
    db, faker, test_user, test_contact
):
    """A tag deleted after a segment was saved must never error the
    segment - it just stops matching, same as a dangling list_id."""
    from app.repositories.tag_repository import TagRepository

    repository = TagRepository(db)
    repository.set_contact_tags(test_contact.id, ["vip"], test_user.id)
    tag = repository.get_by_name("vip")
    repository.delete_tag(tag.id)

    root = _root({"type": "tags", "tag_ids": [str(tag.id)], "op": "in"})
    resolved_ids = {c.id for c in resolve_contacts_query(db, root).all()}

    assert resolved_ids == set()


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
            campaign_id=campaign.id,
            contact_id=test_contact.id,
            opened_at=faker.date_time(),
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
            campaign_id=campaign.id,
            contact_id=test_contact.id,
            opened_at=faker.date_time(),
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
            campaign_id=campaign.id,
            contact_id=test_contact.id,
            clicked_at=faker.date_time(),
        )
    )
    db.commit()

    in_list_only = _contact(db, faker, test_user)
    ContactListRepository(db).add_contact_to_list(test_contact_list.id, in_list_only.id)

    root = _root(
        {
            "op": "and",
            "conditions": [
                {
                    "type": "list_membership",
                    "list_id": str(test_contact_list.id),
                    "op": "in",
                },
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
                {
                    "type": "list_membership",
                    "list_id": str(test_contact_list.id),
                    "op": "in",
                },
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
    ContactListRepository(db).add_contact_to_list(
        test_contact_list.id, also_newsletter.id
    )
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
                {
                    "type": "list_membership",
                    "list_id": str(newsletter.id),
                    "op": "not_in",
                },
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


def test_contact_field_eq(db, faker, test_user):
    acme = _contact(db, faker, test_user, company="Acme Inc")
    other = _contact(db, faker, test_user, company="Globex")

    root = _root(
        {
            "type": "contact_field",
            "field": "company",
            "operator": "==",
            "value": "Acme Inc",
        }
    )
    resolved_ids = {c.id for c in resolve_contacts_query(db, root).all()}

    assert acme.id in resolved_ids
    assert other.id not in resolved_ids


def test_contact_field_ilike(db, faker, test_user):
    acme = _contact(db, faker, test_user, company="Acme Inc")
    other = _contact(db, faker, test_user, company="Globex")

    root = _root(
        {
            "type": "contact_field",
            "field": "company",
            "operator": "ilike",
            "value": "%acme%",
        }
    )
    resolved_ids = {c.id for c in resolve_contacts_query(db, root).all()}

    assert acme.id in resolved_ids
    assert other.id not in resolved_ids


def test_contact_field_in(db, faker, test_user):
    acme = _contact(db, faker, test_user, company="Acme Inc")
    globex = _contact(db, faker, test_user, company="Globex")
    other = _contact(db, faker, test_user, company="Initech")

    root = _root(
        {
            "type": "contact_field",
            "field": "company",
            "operator": "in",
            "value": ["Acme Inc", "Globex"],
        }
    )
    resolved_ids = {c.id for c in resolve_contacts_query(db, root).all()}

    assert acme.id in resolved_ids
    assert globex.id in resolved_ids
    assert other.id not in resolved_ids


def test_contact_field_status(db, faker, test_user):
    active = _contact(db, faker, test_user, status="active")
    inactive = _contact(db, faker, test_user, status="inactive")

    root = _root(
        {
            "type": "contact_field",
            "field": "status",
            "operator": "==",
            "value": "inactive",
        }
    )
    resolved_ids = {c.id for c in resolve_contacts_query(db, root).all()}

    assert inactive.id in resolved_ids
    assert active.id not in resolved_ids


def test_contact_field_status_in(db, faker, test_user):
    active = _contact(db, faker, test_user, status="active")
    pending = _contact(db, faker, test_user, status="pending")
    inactive = _contact(db, faker, test_user, status="inactive")

    root = _root(
        {
            "type": "contact_field",
            "field": "status",
            "operator": "in",
            "value": ["active", "pending"],
        }
    )
    resolved_ids = {c.id for c in resolve_contacts_query(db, root).all()}

    assert active.id in resolved_ids
    assert pending.id in resolved_ids
    assert inactive.id not in resolved_ids


def test_contact_field_rejects_disallowed_operator():
    with pytest.raises(ValueError):
        _root(
            {
                "type": "contact_field",
                "field": "status",
                "operator": "ilike",
                "value": "x",
            }
        )


def test_contact_field_rejects_unknown_contact_type_value():
    with pytest.raises(ValueError):
        _root(
            {
                "type": "contact_field",
                "field": "contact_type",
                "operator": "==",
                "value": "not_a_real_type",
            }
        )


def test_custom_field_string_eq(
    db, faker, test_user, test_contact, test_custom_field_definition
):
    ContactCustomFieldValueRepository(db).set_value(
        contact_id=test_contact.id,
        field_name=test_custom_field_definition.name,
        value="hello",
        set_by_user_id=test_user.id,
    )
    unset_contact = _contact(db, faker, test_user)

    root = _root(
        {
            "type": "custom_field",
            "field_name": test_custom_field_definition.name,
            "operator": "==",
            "value": "hello",
        }
    )
    resolved_ids = {c.id for c in resolve_contacts_query(db, root).all()}

    assert test_contact.id in resolved_ids
    assert unset_contact.id not in resolved_ids


def test_custom_field_number_gte(
    db, faker, test_user, test_contact, test_number_field_definition
):
    """The PRD's own motivating "large family" example: family_member_count >= 3."""
    repository = ContactCustomFieldValueRepository(db)
    repository.set_value(
        contact_id=test_contact.id,
        field_name=test_number_field_definition.name,
        value=3,
        set_by_user_id=test_user.id,
    )
    below_threshold = _contact(db, faker, test_user)
    repository.set_value(
        contact_id=below_threshold.id,
        field_name=test_number_field_definition.name,
        value=1,
        set_by_user_id=test_user.id,
    )

    root = _root(
        {
            "type": "custom_field",
            "field_name": test_number_field_definition.name,
            "operator": ">=",
            "value": 3,
        }
    )
    resolved_ids = {c.id for c in resolve_contacts_query(db, root).all()}

    assert test_contact.id in resolved_ids
    assert below_threshold.id not in resolved_ids


def test_custom_field_undefined_field_raises(db):
    root = _root(
        {
            "type": "custom_field",
            "field_name": "does_not_exist",
            "operator": "==",
            "value": "x",
        }
    )
    with pytest.raises(SegmentResolutionError):
        resolve_count(db, root)


def test_custom_field_operator_not_allowed_for_value_type_raises(
    db, test_number_field_definition
):
    root = _root(
        {
            "type": "custom_field",
            "field_name": test_number_field_definition.name,
            "operator": "ilike",
            "value": "x",
        }
    )
    with pytest.raises(SegmentResolutionError):
        validate_custom_field_references(db, root)


def test_custom_field_and_contact_field_combined(
    db, faker, test_user, test_contact, test_number_field_definition
):
    """ "Company X AND family_member_count >= 3" - user story 6's example."""
    test_contact.company = "Acme Inc"
    db.add(test_contact)
    db.commit()
    ContactCustomFieldValueRepository(db).set_value(
        contact_id=test_contact.id,
        field_name=test_number_field_definition.name,
        value=5,
        set_by_user_id=test_user.id,
    )
    wrong_company = _contact(db, faker, test_user, company="Globex")
    ContactCustomFieldValueRepository(db).set_value(
        contact_id=wrong_company.id,
        field_name=test_number_field_definition.name,
        value=5,
        set_by_user_id=test_user.id,
    )

    root = _root(
        {
            "op": "and",
            "conditions": [
                {
                    "type": "contact_field",
                    "field": "company",
                    "operator": "==",
                    "value": "Acme Inc",
                },
                {
                    "type": "custom_field",
                    "field_name": test_number_field_definition.name,
                    "operator": ">=",
                    "value": 3,
                },
            ],
        }
    )
    resolved_ids = {c.id for c in resolve_contacts_query(db, root).all()}

    assert test_contact.id in resolved_ids
    assert wrong_company.id not in resolved_ids

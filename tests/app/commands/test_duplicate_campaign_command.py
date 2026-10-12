"""Tests for DuplicateCampaignCommand."""

from uuid import uuid4

import pytest

from app.commands.campaign.duplicate_campaign_command import DuplicateCampaignCommand
from app.constants.campaign import CampaignStatus
from app.models.campaign_recipient import CampaignRecipient
from app.repositories.campaign_repository import CampaignRepository
from app.repositories.tag_repository import TagRepository


@pytest.fixture
def sent_campaign(db, draft_campaign, test_contact, test_user):
    """A campaign that has been sent and gathered results: tags, a batch,
    a recipient snapshot, and engagement counts."""
    TagRepository(db).set_campaign_tags(
        draft_campaign.id, ["launch", "q4"], test_user.id
    )
    CampaignRepository(db).mark_sending(
        draft_campaign.id, "batch-xyz", recipient_contact_ids=[test_contact.id]
    )
    draft_campaign.status = CampaignStatus.COMPLETED.value
    draft_campaign.delivered_count = 10
    draft_campaign.opened_count = 4
    draft_campaign.clicked_count = 2
    db.commit()
    db.refresh(draft_campaign)
    return draft_campaign


def test_copies_authored_content_and_audience(db, sent_campaign, setup_another_user):
    copy = DuplicateCampaignCommand(db).execute(sent_campaign.id, setup_another_user.id)

    assert copy.id != sent_campaign.id
    assert copy.name == f"Copy of {sent_campaign.name}"
    assert copy.segment_id == sent_campaign.segment_id
    assert copy.project_id == sent_campaign.project_id
    assert copy.html == sent_campaign.html
    assert copy.layout_id == sent_campaign.layout_id
    assert copy.subject == sent_campaign.subject
    assert copy.from_email == sent_campaign.from_email
    assert copy.template_variables == sent_campaign.template_variables
    assert copy.tags == ["launch", "q4"]
    assert copy.created_by_id == setup_another_user.id


def test_resets_everything_the_send_produced(db, sent_campaign, test_user):
    copy = DuplicateCampaignCommand(db).execute(sent_campaign.id, test_user.id)

    assert copy.status == CampaignStatus.DRAFT.value
    assert copy.batch_id is None
    assert copy.sent_at is None
    assert copy.completed_at is None
    assert copy.delivered_count == 0
    assert copy.bounced_count == 0
    assert copy.complained_count == 0
    assert copy.opened_count == 0
    assert copy.clicked_count == 0
    assert copy.engagement_last_synced_at is None
    assert copy.engagement_polling_expires_at is None
    assert (
        db.query(CampaignRecipient)
        .filter(CampaignRecipient.campaign_id == copy.id)
        .count()
        == 0
    )


def test_source_is_left_untouched(db, sent_campaign, test_user):
    DuplicateCampaignCommand(db).execute(sent_campaign.id, test_user.id)

    db.refresh(sent_campaign)
    assert sent_campaign.status == CampaignStatus.COMPLETED.value
    assert sent_campaign.batch_id == "batch-xyz"
    assert sent_campaign.tags == ["launch", "q4"]


def test_variables_are_copied_not_shared(db, draft_campaign, test_user):
    copy = DuplicateCampaignCommand(db).execute(draft_campaign.id, test_user.id)
    # In-memory, not via the DB: in-place JSONB mutation isn't persisted, so
    # a refresh would pass even if the two campaigns shared one dict.
    copy.template_variables["greeting"] = "Changed"

    assert draft_campaign.template_variables == {"greeting": "Hello"}


def test_not_yet_backfilled_source_carries_its_template(db, draft_campaign, test_user):
    legacy_template_id = uuid4()
    draft_campaign.html = None
    draft_campaign.template_id = legacy_template_id
    db.commit()

    copy = DuplicateCampaignCommand(db).execute(draft_campaign.id, test_user.id)

    assert copy.html is None
    assert copy.template_id == legacy_template_id


def test_backfilled_source_does_not_carry_its_template(db, draft_campaign, test_user):
    draft_campaign.template_id = uuid4()
    db.commit()

    copy = DuplicateCampaignCommand(db).execute(draft_campaign.id, test_user.id)

    assert copy.template_id is None


def test_unknown_campaign_raises(db, test_user):
    with pytest.raises(ValueError, match="not found"):
        DuplicateCampaignCommand(db).execute(uuid4(), test_user.id)

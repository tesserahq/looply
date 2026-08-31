from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.constants.campaign import CampaignStatus
from app.repositories.campaign_repository import CampaignRepository
from app.repositories.contact_list_repository import ContactListRepository
from app.schemas.campaign import CampaignCreate, CampaignUpdate


def test_create_campaign(db, faker, test_user, test_segment):
    repository = CampaignRepository(db)
    campaign = repository.create_campaign(
        CampaignCreate(
            name=faker.catch_phrase(),
            segment_id=test_segment.id,
            created_by_id=test_user.id,
        )
    )

    assert campaign.id is not None
    assert campaign.status == CampaignStatus.DRAFT.value
    assert campaign.segment_id == test_segment.id
    assert campaign.template_variables == {}
    assert campaign.tags == []


def test_get_campaign(db, draft_campaign):
    repository = CampaignRepository(db)
    campaign = repository.get_campaign(draft_campaign.id)

    assert campaign is not None
    assert campaign.id == draft_campaign.id


def test_get_campaign_not_found(db):
    repository = CampaignRepository(db)
    assert repository.get_campaign(uuid4()) is None


def test_get_campaigns_by_status(db, draft_campaign, sending_campaign):
    repository = CampaignRepository(db)

    sending = repository.get_campaigns_by_status(CampaignStatus.SENDING.value)
    sending_ids = [c.id for c in sending]

    assert sending_campaign.id in sending_ids
    assert draft_campaign.id not in sending_ids


def test_update_campaign(db, draft_campaign, faker):
    original_name = draft_campaign.name
    new_name = faker.catch_phrase()
    repository = CampaignRepository(db)
    updated = repository.update_campaign(
        draft_campaign.id, CampaignUpdate(name=new_name)
    )

    assert updated is not None
    assert updated.name == new_name
    assert updated.name != original_name


def test_delete_campaign(db, draft_campaign):
    repository = CampaignRepository(db)
    assert repository.delete_campaign(draft_campaign.id) is True
    assert repository.get_campaign(draft_campaign.id) is None


def test_mark_sending(db, draft_campaign):
    repository = CampaignRepository(db)
    updated = repository.mark_sending(draft_campaign.id, "batch-123")

    assert updated.status == CampaignStatus.SENDING.value
    assert updated.batch_id == "batch-123"
    assert updated.sent_at is not None


def test_mark_sending_records_recipient_snapshot(db, draft_campaign, test_contact):
    from app.models.campaign_recipient import CampaignRecipient

    repository = CampaignRepository(db)
    repository.mark_sending(
        draft_campaign.id, "batch-123", recipient_contact_ids=[test_contact.id]
    )

    recipients = (
        db.query(CampaignRecipient)
        .filter(CampaignRecipient.campaign_id == draft_campaign.id)
        .all()
    )
    assert len(recipients) == 1
    assert recipients[0].contact_id == test_contact.id


def test_mark_sending_no_recipient_rows_when_campaign_not_draft(
    db, sending_campaign, test_contact
):
    from app.models.campaign_recipient import CampaignRecipient

    repository = CampaignRepository(db)
    updated = repository.mark_sending(
        sending_campaign.id, "batch-456", recipient_contact_ids=[test_contact.id]
    )

    assert updated is None
    recipients = (
        db.query(CampaignRecipient)
        .filter(CampaignRecipient.campaign_id == sending_campaign.id)
        .all()
    )
    assert recipients == []


def test_mark_completed(db, sending_campaign):
    repository = CampaignRepository(db)
    completed_at = datetime.now(timezone.utc)
    updated = repository.mark_completed(sending_campaign.id, completed_at)

    assert updated.status == CampaignStatus.COMPLETED.value
    assert updated.completed_at is not None


def test_mark_completed_sets_engagement_polling_expiry(db, sending_campaign):
    from app.config import get_settings

    repository = CampaignRepository(db)
    completed_at = datetime.now(timezone.utc)
    updated = repository.mark_completed(sending_campaign.id, completed_at)

    expected_expiry = completed_at.replace(tzinfo=None) + timedelta(
        days=get_settings().engagement_polling_window_days
    )
    assert updated.engagement_polling_expires_at == expected_expiry


def test_get_campaigns_within_engagement_window(db, sending_campaign, draft_campaign):
    repository = CampaignRepository(db)
    now = datetime.now(timezone.utc)
    repository.mark_completed(sending_campaign.id, now)

    within_window = repository.get_campaigns_within_engagement_window(now)
    assert [c.id for c in within_window] == [sending_campaign.id]

    outside_window = repository.get_campaigns_within_engagement_window(
        now + timedelta(days=999)
    )
    assert outside_window == []


def test_update_campaign_engagement_counts_round_trips(db, sending_campaign):
    repository = CampaignRepository(db)
    synced_at = datetime.now(timezone.utc)
    repository.update_campaign_engagement_counts(
        sending_campaign.id,
        delivered_count=10,
        bounced_count=1,
        complained_count=0,
        opened_count=5,
        clicked_count=2,
        synced_at=synced_at,
    )
    db.commit()

    updated = repository.get_campaign(sending_campaign.id)
    assert updated.delivered_count == 10
    assert updated.bounced_count == 1
    assert updated.complained_count == 0
    assert updated.opened_count == 5
    assert updated.clicked_count == 2
    assert updated.engagement_last_synced_at == synced_at.replace(tzinfo=None)


def test_record_recipient_engagement_does_not_overwrite_existing_timestamp(
    db, sending_campaign, test_contact
):
    from app.models.campaign_recipient import CampaignRecipient

    first_open = datetime.now(timezone.utc) - timedelta(days=1)
    recipient = CampaignRecipient(
        campaign_id=sending_campaign.id,
        contact_id=test_contact.id,
        opened_at=first_open,
    )
    db.add(recipient)
    db.commit()

    repository = CampaignRepository(db)
    later_open = datetime.now(timezone.utc)
    repository.record_recipient_engagement(
        sending_campaign.id, test_contact.id, opened_at=later_open, clicked_at=None
    )
    db.commit()
    db.refresh(recipient)

    assert recipient.opened_at == first_open.replace(tzinfo=None)


def test_mark_failed(db, draft_campaign):
    repository = CampaignRepository(db)
    updated = repository.mark_failed(draft_campaign.id)

    assert updated.status == CampaignStatus.FAILED.value


def test_get_eligible_recipients_for_segment_filters_inactive(
    db,
    test_contact_list,
    test_segment,
    test_contact,
    inactive_contact,
):
    """Contact.email is unique (see
    docs/prds/0003-event-driven-contact-resolution.md), so two contacts can no
    longer share an email - get_eligible_recipients_for_segment's DISTINCT ON
    email is now purely defensive. This only exercises the active-only filter."""
    contact_list_repository = ContactListRepository(db)
    contact_list_repository.add_contact_to_list(test_contact_list.id, test_contact.id)
    contact_list_repository.add_contact_to_list(
        test_contact_list.id, inactive_contact.id
    )

    repository = CampaignRepository(db)
    recipients = repository.get_eligible_recipients_for_segment(test_segment)

    emails = [contact.email for contact in recipients]
    assert emails.count(test_contact.email) == 1
    assert inactive_contact.email not in emails


def test_get_eligible_recipients_for_segment_excludes_no_email(
    db, test_contact_list, test_segment, test_user, faker
):
    from app.models.contact import Contact

    contact_list_repository = ContactListRepository(db)
    no_email_contact = Contact(
        first_name=faker.first_name(),
        last_name=faker.last_name(),
        email=None,
        contact_type="business",
        phone_type="work",
        is_active=True,
        created_by_id=test_user.id,
    )
    db.add(no_email_contact)
    db.commit()
    db.refresh(no_email_contact)
    contact_list_repository.add_contact_to_list(
        test_contact_list.id, no_email_contact.id
    )

    repository = CampaignRepository(db)
    recipients = repository.get_eligible_recipients_for_segment(test_segment)

    assert no_email_contact.id not in [c.id for c in recipients]

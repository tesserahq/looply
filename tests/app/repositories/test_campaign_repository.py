from datetime import datetime, timezone
from uuid import uuid4

from app.constants.campaign import CampaignStatus
from app.repositories.campaign_repository import CampaignRepository
from app.repositories.contact_list_repository import ContactListRepository
from app.schemas.campaign import CampaignCreate, CampaignUpdate


def test_create_campaign(db, faker, test_user, test_contact_list):
    repository = CampaignRepository(db)
    campaign = repository.create_campaign(
        CampaignCreate(
            name=faker.catch_phrase(),
            contact_list_id=test_contact_list.id,
            created_by_id=test_user.id,
        )
    )

    assert campaign.id is not None
    assert campaign.status == CampaignStatus.DRAFT.value
    assert campaign.contact_list_id == test_contact_list.id
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


def test_mark_completed(db, sending_campaign):
    repository = CampaignRepository(db)
    completed_at = datetime.now(timezone.utc)
    updated = repository.mark_completed(sending_campaign.id, completed_at)

    assert updated.status == CampaignStatus.COMPLETED.value
    assert updated.completed_at is not None


def test_mark_failed(db, draft_campaign):
    repository = CampaignRepository(db)
    updated = repository.mark_failed(draft_campaign.id)

    assert updated.status == CampaignStatus.FAILED.value


def test_get_eligible_campaign_recipients_filters_and_dedupes(
    db, test_contact_list, test_contact, inactive_contact, faker, test_user
):
    from app.models.contact import Contact

    contact_list_repository = ContactListRepository(db)
    contact_list_repository.add_contact_to_list(test_contact_list.id, test_contact.id)
    contact_list_repository.add_contact_to_list(
        test_contact_list.id, inactive_contact.id
    )

    # A second, active contact sharing the same email as test_contact -- the
    # eligible-recipients query must dedupe by email.
    duplicate_email_contact = Contact(
        first_name=faker.first_name(),
        last_name=faker.last_name(),
        email=test_contact.email,
        contact_type="business",
        phone_type="work",
        is_active=True,
        created_by_id=test_user.id,
    )
    db.add(duplicate_email_contact)
    db.commit()
    db.refresh(duplicate_email_contact)
    contact_list_repository.add_contact_to_list(
        test_contact_list.id, duplicate_email_contact.id
    )

    recipients = contact_list_repository.get_eligible_campaign_recipients(
        test_contact_list.id
    )

    emails = [contact.email for contact in recipients]
    assert emails.count(test_contact.email) == 1
    assert inactive_contact.email not in emails


def test_get_eligible_campaign_recipients_excludes_no_email(
    db, test_contact_list, test_user, faker
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

    recipients = contact_list_repository.get_eligible_campaign_recipients(
        test_contact_list.id
    )

    assert no_email_contact.id not in [c.id for c in recipients]

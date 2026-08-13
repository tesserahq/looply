"""Tests for SendCampaignCommand."""

from uuid import uuid4

import pytest
from tessera_sdk.clients.sendly import SendBroadcastResponse

from app.commands.campaign.send_campaign_command import SendCampaignCommand
from app.constants.campaign import CampaignStatus
from app.models.campaign_recipient import CampaignRecipient
from app.repositories.campaign_repository import CampaignRepository
from app.repositories.contact_list_repository import ContactListRepository


class FakeSendlyClient:
    """Fake SendlyClient injected in place of the real SDK client in tests."""

    def __init__(self, response=None, error=None, fail_times=0):
        self.response = response or SendBroadcastResponse(
            batch_id="batch-abc", queued_count=1, suppressed_count=0
        )
        self.error = error
        self.fail_times = fail_times
        self.calls = []

    def send_broadcast(self, request):
        self.calls.append(request)
        if self.fail_times > 0 and len(self.calls) <= self.fail_times:
            raise (self.error or Exception("simulated Sendly failure"))
        if self.error and self.fail_times == 0:
            raise self.error
        return self.response


def _add_eligible_contact(db, contact_list, contact):
    ContactListRepository(db).add_contact_to_list(contact_list.id, contact.id)


def test_send_campaign_success(db, draft_campaign, test_contact_list, test_contact):
    _add_eligible_contact(db, test_contact_list, test_contact)

    fake_client = FakeSendlyClient()
    command = SendCampaignCommand(db, sendly_client=fake_client)

    result = command.execute(draft_campaign.id)

    assert result.status == CampaignStatus.SENDING.value
    assert result.batch_id == "batch-abc"
    assert result.sent_at is not None
    assert command.last_recipient_count == 1

    # idempotency_key must be derived purely from the campaign id
    sent_request = fake_client.calls[0]
    assert sent_request.idempotency_key == f"campaign:{draft_campaign.id}"
    assert len(sent_request.recipients) == 1
    assert sent_request.recipients[0].email == test_contact.email
    assert sent_request.recipients[0].attributes["job_title"] == test_contact.job
    assert sent_request.recipients[0].attributes["company"] == test_contact.company

    recipient_rows = (
        db.query(CampaignRecipient)
        .filter(CampaignRecipient.campaign_id == draft_campaign.id)
        .all()
    )
    assert len(recipient_rows) == 1
    assert recipient_rows[0].contact_id == test_contact.id


def test_send_campaign_not_found(db):
    command = SendCampaignCommand(db, sendly_client=FakeSendlyClient())

    with pytest.raises(ValueError, match="not found"):
        command.execute(uuid4())


def test_send_campaign_not_draft(db, sending_campaign):
    command = SendCampaignCommand(db, sendly_client=FakeSendlyClient())

    with pytest.raises(ValueError, match="draft"):
        command.execute(sending_campaign.id)


def test_send_campaign_no_template_id(db, draft_campaign):
    draft_campaign.template_id = None
    db.commit()

    command = SendCampaignCommand(db, sendly_client=FakeSendlyClient())

    with pytest.raises(ValueError, match="template_id"):
        command.execute(draft_campaign.id)


def test_send_campaign_no_eligible_recipients(db, draft_campaign):
    command = SendCampaignCommand(db, sendly_client=FakeSendlyClient())

    with pytest.raises(ValueError, match="no eligible recipients"):
        command.execute(draft_campaign.id)


def test_send_campaign_excludes_inactive_and_no_email_contacts(
    db, draft_campaign, test_contact_list, inactive_contact
):
    _add_eligible_contact(db, test_contact_list, inactive_contact)

    command = SendCampaignCommand(db, sendly_client=FakeSendlyClient())

    with pytest.raises(ValueError, match="no eligible recipients"):
        command.execute(draft_campaign.id)


def test_send_campaign_marks_failed_after_exhausted_retries(
    db, draft_campaign, test_contact_list, test_contact, monkeypatch
):
    monkeypatch.setattr(
        "app.commands.campaign.send_campaign_command.time.sleep", lambda *_: None
    )
    _add_eligible_contact(db, test_contact_list, test_contact)

    fake_client = FakeSendlyClient(error=Exception("Sendly unavailable"), fail_times=99)
    command = SendCampaignCommand(db, sendly_client=fake_client)

    with pytest.raises(Exception, match="Failed to send campaign"):
        command.execute(draft_campaign.id)

    campaign = CampaignRepository(db).get_campaign(draft_campaign.id)
    assert campaign.status == CampaignStatus.FAILED.value
    # Every attempt reuses the same idempotency key, so retries are safe.
    assert len({c.idempotency_key for c in fake_client.calls}) == 1

    # A failed send must not leave a recipient snapshot behind.
    recipient_rows = (
        db.query(CampaignRecipient)
        .filter(CampaignRecipient.campaign_id == draft_campaign.id)
        .all()
    )
    assert recipient_rows == []


def test_send_campaign_retries_before_succeeding(
    db, draft_campaign, test_contact_list, test_contact, monkeypatch
):
    monkeypatch.setattr(
        "app.commands.campaign.send_campaign_command.time.sleep", lambda *_: None
    )
    _add_eligible_contact(db, test_contact_list, test_contact)

    fake_client = FakeSendlyClient(fail_times=2)
    command = SendCampaignCommand(db, sendly_client=fake_client)

    result = command.execute(draft_campaign.id)

    assert result.status == CampaignStatus.SENDING.value
    assert len(fake_client.calls) == 3

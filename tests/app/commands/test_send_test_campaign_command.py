"""Tests for SendTestCampaignCommand."""

from datetime import datetime
from uuid import uuid4

import pytest
from tessera_sdk.clients.sendly import CreateEmailResponse, RenderResponse

from app.commands.campaign.send_test_campaign_command import (
    CampaignTestSendError,
    SendTestCampaignCommand,
)
from app.constants.campaign import CampaignStatus
from app.models.campaign_recipient import CampaignRecipient
from app.schemas.contact import ContactStatus


class FakeSendlyClient:
    """Fake SendlyClient injected in place of the real SDK client in tests."""

    def __init__(self, status="sent", error_message=None):
        self.status = status
        self.error_message = error_message
        self.render_calls = []
        self.email_calls = []

    def render(self, request):
        self.render_calls.append(request)
        return RenderResponse(
            html=f"<layout>{request.html}</layout>",
            subject=request.subject,
        )

    def create_email(self, request):
        self.email_calls.append(request)
        return CreateEmailResponse(
            from_email=str(request.from_email),
            to_email=str(request.to[0]),
            subject=request.subject,
            body=request.html,
            status=self.status,
            provider="fake",
            provider_message_id="msg-123",
            id="email-123",
            error_message=self.error_message,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )


def test_send_test_campaign_success(db, draft_campaign, test_contact):
    fake_client = FakeSendlyClient()
    command = SendTestCampaignCommand(db, sendly_client=fake_client)

    response = command.execute(draft_campaign.id, test_contact.id)

    assert response.id == "email-123"
    assert response.status == "sent"

    render_request = fake_client.render_calls[0]
    assert render_request.html == draft_campaign.html
    assert render_request.subject == draft_campaign.subject
    assert render_request.layout_id == draft_campaign.layout_id
    # Same merge variables a real broadcast gives each recipient.
    assert render_request.template_variables == {
        "greeting": "Hello",
        "first_name": test_contact.first_name,
        "company": test_contact.company,
        "job_title": test_contact.job,
        "contact_type": test_contact.contact_type,
    }

    email_request = fake_client.email_calls[0]
    assert email_request.project_id == draft_campaign.project_id
    assert str(email_request.from_email) == draft_campaign.from_email
    assert email_request.subject == f"[TEST] {draft_campaign.subject}"
    assert email_request.html == f"<layout>{draft_campaign.html}</layout>"
    assert [str(address) for address in email_request.to] == [test_contact.email]


def test_send_test_campaign_leaves_campaign_as_draft(db, draft_campaign, test_contact):
    command = SendTestCampaignCommand(db, sendly_client=FakeSendlyClient())

    command.execute(draft_campaign.id, test_contact.id)

    db.refresh(draft_campaign)
    assert draft_campaign.status == CampaignStatus.DRAFT.value
    assert draft_campaign.batch_id is None
    recipient_rows = (
        db.query(CampaignRecipient)
        .filter(CampaignRecipient.campaign_id == draft_campaign.id)
        .all()
    )
    assert recipient_rows == []


def test_send_test_campaign_campaign_not_found(db, test_contact):
    command = SendTestCampaignCommand(db, sendly_client=FakeSendlyClient())

    with pytest.raises(ValueError, match="not found"):
        command.execute(uuid4(), test_contact.id)


def test_send_test_campaign_not_draft(db, draft_campaign, test_contact):
    draft_campaign.status = CampaignStatus.SENDING.value
    db.commit()
    fake_client = FakeSendlyClient()
    command = SendTestCampaignCommand(db, sendly_client=fake_client)

    with pytest.raises(ValueError, match="is not in draft status"):
        command.execute(draft_campaign.id, test_contact.id)

    assert fake_client.render_calls == []
    assert fake_client.email_calls == []


def test_send_test_campaign_missing_content(db, draft_campaign, test_contact):
    draft_campaign.subject = None
    db.commit()
    fake_client = FakeSendlyClient()
    command = SendTestCampaignCommand(db, sendly_client=fake_client)

    with pytest.raises(ValueError, match="missing content required to send: subject"):
        command.execute(draft_campaign.id, test_contact.id)

    assert fake_client.render_calls == []
    assert fake_client.email_calls == []


def test_send_test_campaign_contact_not_found(db, draft_campaign):
    fake_client = FakeSendlyClient()
    command = SendTestCampaignCommand(db, sendly_client=fake_client)

    with pytest.raises(ValueError, match="not found"):
        command.execute(draft_campaign.id, uuid4())

    assert fake_client.email_calls == []


def test_send_test_campaign_deleted_contact_not_found(db, draft_campaign, test_contact):
    test_contact.deleted_at = datetime.now()
    db.commit()
    fake_client = FakeSendlyClient()
    command = SendTestCampaignCommand(db, sendly_client=fake_client)

    with pytest.raises(ValueError, match="not found"):
        command.execute(draft_campaign.id, test_contact.id)

    assert fake_client.email_calls == []


@pytest.mark.parametrize(
    "inactive_status", [ContactStatus.INACTIVE.value, ContactStatus.PENDING.value]
)
def test_send_test_campaign_inactive_contact(
    db, draft_campaign, test_contact, inactive_status
):
    test_contact.status = inactive_status
    db.commit()
    fake_client = FakeSendlyClient()
    command = SendTestCampaignCommand(db, sendly_client=fake_client)

    with pytest.raises(ValueError, match="is not active"):
        command.execute(draft_campaign.id, test_contact.id)

    assert fake_client.email_calls == []


def test_send_test_campaign_contact_without_email(db, draft_campaign, test_contact):
    test_contact.email = None
    db.commit()
    fake_client = FakeSendlyClient()
    command = SendTestCampaignCommand(db, sendly_client=fake_client)

    with pytest.raises(ValueError, match="has no email address"):
        command.execute(draft_campaign.id, test_contact.id)

    assert fake_client.email_calls == []


def test_send_test_campaign_contact_with_invalid_email(
    db, draft_campaign, test_contact
):
    test_contact.email = "not-an-email"
    db.commit()
    fake_client = FakeSendlyClient()
    command = SendTestCampaignCommand(db, sendly_client=fake_client)

    with pytest.raises(ValueError, match="invalid email address"):
        command.execute(draft_campaign.id, test_contact.id)

    assert fake_client.email_calls == []


def test_send_test_campaign_sendly_failure(db, draft_campaign, test_contact):
    fake_client = FakeSendlyClient(status="failed", error_message="bounced at relay")
    command = SendTestCampaignCommand(db, sendly_client=fake_client)

    with pytest.raises(CampaignTestSendError, match="bounced at relay"):
        command.execute(draft_campaign.id, test_contact.id)

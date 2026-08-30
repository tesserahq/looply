"""Tests for the campaign engagement polling task."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from tessera_sdk.clients.sendly import GetBroadcastResponse
from tessera_sdk.clients.sendly.schemas.broadcast_recipient_result import (
    BroadcastRecipientResult,
)

from app.models.campaign_recipient import CampaignRecipient
from app.repositories.campaign_repository import CampaignRepository
from app.tasks.poll_campaign_engagement import _poll_campaign_engagement


class FakeSendlyClient:
    def __init__(self, broadcasts=None, recipients=None, error_batch_ids=None):
        self.broadcasts = broadcasts or {}
        self.recipients = recipients or {}
        self.error_batch_ids = error_batch_ids or set()
        self.calls = []

    def iter_broadcast_recipients(self, batch_id, project_id=None):
        self.calls.append(("iter_broadcast_recipients", batch_id, project_id))
        if batch_id in self.error_batch_ids:
            raise Exception("Sendly lookup failed")
        yield from self.recipients.get(batch_id, [])

    def get_broadcast(self, batch_id, project_id=None):
        self.calls.append(("get_broadcast", batch_id, project_id))
        if batch_id in self.error_batch_ids:
            raise Exception("Sendly lookup failed")
        return self.broadcasts[batch_id]


def _completed_campaign(db, faker, test_user, test_contact_list, *, expires_in_days=3):
    from app.constants.campaign import CampaignStatus
    from app.models.campaign import Campaign

    now = datetime.now(timezone.utc)
    campaign = Campaign(
        name=faker.catch_phrase(),
        status=CampaignStatus.COMPLETED.value,
        contact_list_id=test_contact_list.id,
        project_id=uuid4(),
        template_id=uuid4(),
        batch_id=faker.uuid4(),
        completed_at=now,
        engagement_polling_expires_at=now + timedelta(days=expires_in_days),
        created_by_id=test_user.id,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


def _broadcast_response(batch_id, **overrides):
    defaults = dict(
        batch_id=batch_id,
        queued_count=1,
        suppressed_count=0,
        prepared_count=1,
        finished=True,
        delivered_count=1,
        bounced_count=0,
        complained_count=0,
        opened_count=1,
        clicked_count=0,
    )
    defaults.update(overrides)
    return GetBroadcastResponse(**defaults)


def _recipient_result(contact_id, **overrides):
    defaults = dict(
        id=uuid4(),
        client_reference_id=contact_id,
        email="test@example.com",
        suppressed=False,
        prepared=True,
        email_id=uuid4(),
        email_status="delivered",
        opened_at=None,
        clicked_at=None,
    )
    defaults.update(overrides)
    return BroadcastRecipientResult(**defaults)


def test_updates_recipient_and_campaign_from_stubbed_response(
    db, faker, test_user, test_contact_list, test_contact, monkeypatch
):
    campaign = _completed_campaign(db, faker, test_user, test_contact_list)
    db.add(CampaignRecipient(campaign_id=campaign.id, contact_id=test_contact.id))
    db.commit()

    opened_at = datetime.now(timezone.utc) - timedelta(hours=1)
    fake_client = FakeSendlyClient(
        broadcasts={campaign.batch_id: _broadcast_response(campaign.batch_id)},
        recipients={
            campaign.batch_id: [_recipient_result(test_contact.id, opened_at=opened_at)]
        },
    )
    monkeypatch.setattr(
        "app.tasks.poll_campaign_engagement.build_sendly_client", lambda: fake_client
    )

    _poll_campaign_engagement(db)

    updated_recipient = (
        db.query(CampaignRecipient)
        .filter(
            CampaignRecipient.campaign_id == campaign.id,
            CampaignRecipient.contact_id == test_contact.id,
        )
        .first()
    )
    assert updated_recipient.opened_at == opened_at.replace(tzinfo=None)
    assert updated_recipient.clicked_at is None

    updated_campaign = CampaignRepository(db).get_campaign(campaign.id)
    assert updated_campaign.delivered_count == 1
    assert updated_campaign.opened_count == 1
    assert updated_campaign.engagement_last_synced_at is not None


def test_skips_campaign_outside_polling_window(
    db, faker, test_user, test_contact_list, monkeypatch
):
    campaign = _completed_campaign(
        db, faker, test_user, test_contact_list, expires_in_days=-1
    )
    fake_client = FakeSendlyClient()
    monkeypatch.setattr(
        "app.tasks.poll_campaign_engagement.build_sendly_client", lambda: fake_client
    )

    _poll_campaign_engagement(db)

    assert fake_client.calls == []
    updated_campaign = CampaignRepository(db).get_campaign(campaign.id)
    assert updated_campaign.engagement_last_synced_at is None


def test_one_campaign_failure_does_not_stop_others(
    db, faker, test_user, test_contact_list, monkeypatch
):
    failing = _completed_campaign(db, faker, test_user, test_contact_list)
    succeeding = _completed_campaign(db, faker, test_user, test_contact_list)

    fake_client = FakeSendlyClient(
        broadcasts={succeeding.batch_id: _broadcast_response(succeeding.batch_id)},
        recipients={succeeding.batch_id: []},
        error_batch_ids={failing.batch_id},
    )
    monkeypatch.setattr(
        "app.tasks.poll_campaign_engagement.build_sendly_client", lambda: fake_client
    )

    # Must not raise.
    _poll_campaign_engagement(db)

    repo = CampaignRepository(db)
    assert repo.get_campaign(failing.id).engagement_last_synced_at is None
    assert repo.get_campaign(succeeding.id).engagement_last_synced_at is not None

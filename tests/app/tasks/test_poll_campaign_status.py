"""Tests for the campaign status polling task."""

from tessera_sdk.clients.sendly import GetBroadcastResponse

from app.constants.campaign import CampaignStatus
from app.repositories.campaign_repository import CampaignRepository
from app.tasks.poll_campaign_status import _poll_sending_campaigns


class FakeSendlyClient:
    def __init__(self, responses=None, error_batch_ids=None):
        self.responses = responses or {}
        self.error_batch_ids = error_batch_ids or set()
        self.calls = []

    def get_broadcast(self, batch_id, project_id=None):
        self.calls.append((batch_id, project_id))
        if batch_id in self.error_batch_ids:
            raise Exception("Sendly lookup failed")
        return self.responses[batch_id]


def test_poll_marks_completed_when_finished(db, sending_campaign, monkeypatch):
    fake_client = FakeSendlyClient(
        responses={
            sending_campaign.batch_id: GetBroadcastResponse(
                batch_id=sending_campaign.batch_id,
                queued_count=10,
                suppressed_count=0,
                prepared_count=10,
                finished=True,
                delivered_count=10,
                bounced_count=0,
                complained_count=0,
                opened_count=0,
                clicked_count=0,
            )
        }
    )
    monkeypatch.setattr(
        "app.tasks.poll_campaign_status.build_sendly_client", lambda: fake_client
    )

    _poll_sending_campaigns(db)

    updated = CampaignRepository(db).get_campaign(sending_campaign.id)
    assert updated.status == CampaignStatus.COMPLETED.value
    assert updated.completed_at is not None


def test_poll_leaves_status_when_not_finished(db, sending_campaign, monkeypatch):
    fake_client = FakeSendlyClient(
        responses={
            sending_campaign.batch_id: GetBroadcastResponse(
                batch_id=sending_campaign.batch_id,
                queued_count=10,
                suppressed_count=0,
                prepared_count=4,
                finished=False,
                delivered_count=4,
                bounced_count=0,
                complained_count=0,
                opened_count=0,
                clicked_count=0,
            )
        }
    )
    monkeypatch.setattr(
        "app.tasks.poll_campaign_status.build_sendly_client", lambda: fake_client
    )

    _poll_sending_campaigns(db)

    updated = CampaignRepository(db).get_campaign(sending_campaign.id)
    assert updated.status == CampaignStatus.SENDING.value
    assert updated.completed_at is None


def test_poll_swallows_errors_and_never_marks_failed(db, sending_campaign, monkeypatch):
    fake_client = FakeSendlyClient(error_batch_ids={sending_campaign.batch_id})
    monkeypatch.setattr(
        "app.tasks.poll_campaign_status.build_sendly_client", lambda: fake_client
    )

    # Must not raise, and must not touch the campaign's status.
    _poll_sending_campaigns(db)

    updated = CampaignRepository(db).get_campaign(sending_campaign.id)
    assert updated.status == CampaignStatus.SENDING.value


def test_poll_continues_after_one_campaign_errors(
    db,
    sending_campaign,
    draft_campaign,
    faker,
    test_user,
    test_contact_list,
    monkeypatch,
):
    from app.models.campaign import Campaign

    other_sending = Campaign(
        name=faker.catch_phrase(),
        status=CampaignStatus.SENDING.value,
        contact_list_id=test_contact_list.id,
        batch_id=faker.uuid4(),
        created_by_id=test_user.id,
    )
    db.add(other_sending)
    db.commit()
    db.refresh(other_sending)

    fake_client = FakeSendlyClient(
        responses={
            other_sending.batch_id: GetBroadcastResponse(
                batch_id=other_sending.batch_id,
                queued_count=1,
                suppressed_count=0,
                prepared_count=1,
                finished=True,
                delivered_count=1,
                bounced_count=0,
                complained_count=0,
                opened_count=0,
                clicked_count=0,
            )
        },
        error_batch_ids={sending_campaign.batch_id},
    )
    monkeypatch.setattr(
        "app.tasks.poll_campaign_status.build_sendly_client", lambda: fake_client
    )

    _poll_sending_campaigns(db)

    repo = CampaignRepository(db)
    assert repo.get_campaign(other_sending.id).status == CampaignStatus.COMPLETED.value
    assert repo.get_campaign(sending_campaign.id).status == CampaignStatus.SENDING.value

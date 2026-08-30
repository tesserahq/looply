"""Celery beat task: refresh engagement data for recently completed campaigns."""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from tessera_sdk.clients.sendly import SendlyClient

from app.core.celery_app import celery_app
from app.db import SessionLocal
from app.integrations.sendly_client_factory import build_sendly_client
from app.models.campaign import Campaign
from app.repositories.campaign_repository import CampaignRepository

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.poll_campaign_engagement")
def poll_campaign_engagement() -> None:
    """Entry point invoked by Celery beat."""
    db = SessionLocal()
    try:
        _poll_campaign_engagement(db)
    finally:
        db.close()


def _poll_campaign_engagement(db: Session) -> None:
    """
    Refresh opened_at/clicked_at on each completed campaign's recipients,
    and the campaign's own result counts, for as long as that campaign is
    still inside its bounded polling window (see
    CampaignRepository.mark_completed).

    Per-campaign try/except, following poll_campaign_status's pattern: a
    failed lookup for one campaign must not stop the others, and must leave
    that campaign's engagement_last_synced_at untouched, since a partial
    pass should never be reported as a fully synced one.
    """
    campaign_repository = CampaignRepository(db)
    sendly_client = build_sendly_client()

    campaigns = campaign_repository.get_campaigns_within_engagement_window(
        datetime.now(timezone.utc)
    )
    for campaign in campaigns:
        campaign_id, batch_id = campaign.id, campaign.batch_id
        try:
            # A SAVEPOINT, not a plain commit/rollback: on failure this
            # undoes only this campaign's own writes, leaving prior
            # campaigns' already-committed results (and the outer session)
            # untouched, so one bad batch can't clobber the rest.
            with db.begin_nested():
                _sync_campaign_engagement(campaign_repository, sendly_client, campaign)
            db.commit()
        except Exception:
            logger.exception(
                "Failed to poll Sendly engagement for campaign %s (batch_id=%s)",
                campaign_id,
                batch_id,
            )


def _sync_campaign_engagement(
    campaign_repository: CampaignRepository,
    sendly_client: SendlyClient,
    campaign: Campaign,
) -> None:
    project_id = str(campaign.project_id) if campaign.project_id else None

    for result in sendly_client.iter_broadcast_recipients(
        batch_id=campaign.batch_id, project_id=project_id
    ):
        # client_reference_id is contact.id, set at send time
        # (_to_broadcast_recipient) - a result missing it predates that
        # change or came from a request that didn't set it, so it can't be
        # matched back to a recipient.
        if result.client_reference_id is None:
            continue
        campaign_repository.record_recipient_engagement(
            campaign.id,
            result.client_reference_id,
            opened_at=result.opened_at,
            clicked_at=result.clicked_at,
        )

    broadcast = sendly_client.get_broadcast(campaign.batch_id, project_id=project_id)
    campaign_repository.update_campaign_engagement_counts(
        campaign.id,
        delivered_count=broadcast.delivered_count,
        bounced_count=broadcast.bounced_count,
        complained_count=broadcast.complained_count,
        opened_count=broadcast.opened_count,
        clicked_count=broadcast.clicked_count,
        synced_at=datetime.now(timezone.utc),
    )

"""Celery beat task: refresh engagement data for recently completed campaigns."""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session
from tessera_sdk.clients.sendly import GetBroadcastResponse, SendlyClient
from tessera_sdk.clients.sendly.schemas.broadcast_recipient_result import (
    BroadcastRecipientResult,
)

from app.core.celery_app import celery_app
from app.db import savepoint, session_scope
from app.integrations.sendly_client_factory import build_sendly_client
from app.repositories.campaign_repository import CampaignRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _CampaignEngagement:
    recipients: list[BroadcastRecipientResult]
    broadcast: GetBroadcastResponse


@celery_app.task(name="app.tasks.poll_campaign_engagement")
def poll_campaign_engagement() -> None:
    """Entry point invoked by Celery beat."""
    with session_scope() as db:
        _poll_campaign_engagement(db)


def _poll_campaign_engagement(db: Session) -> None:
    """
    Refresh opened_at/clicked_at on each completed campaign's recipients,
    and the campaign's own result counts, for as long as that campaign is
    still inside its bounded polling window (see
    CampaignRepository.mark_completed).

    Each campaign is its own phase: Sendly is queried with no database
    transaction open, then that campaign's writes run in a savepoint and are
    committed. A failed lookup or write for one campaign therefore cannot
    stop the others or undo their already-committed results, and leaves that
    campaign's engagement_last_synced_at untouched, since a partial pass
    should never be reported as a fully synced one.
    """
    campaign_repository = CampaignRepository(db)
    sendly_client = build_sendly_client()

    campaigns = [
        (
            campaign.id,
            campaign.batch_id,
            str(campaign.project_id) if campaign.project_id else None,
        )
        for campaign in campaign_repository.get_campaigns_within_engagement_window(
            datetime.now(timezone.utc)
        )
    ]
    # commit: campaigns_selected. Release the read transaction before calling
    # Sendly.
    db.commit()

    for campaign_id, batch_id, project_id in campaigns:
        try:
            engagement = _fetch_campaign_engagement(sendly_client, batch_id, project_id)
            with savepoint(db):
                _record_campaign_engagement(
                    campaign_repository, campaign_id, engagement
                )
            # commit: campaign_engagement_synced. Per-campaign checkpoint;
            # also releases the connection before the next Sendly call.
            db.commit()
        except Exception:
            logger.exception(
                "Failed to poll Sendly engagement for campaign %s (batch_id=%s)",
                campaign_id,
                batch_id,
            )


def _fetch_campaign_engagement(
    sendly_client: SendlyClient, batch_id: str, project_id: Optional[str]
) -> _CampaignEngagement:
    """Read a campaign's engagement from Sendly. No database access."""
    # client_reference_id is contact.id, set at send time
    # (_to_broadcast_recipient) - a result missing it predates that change or
    # came from a request that didn't set it, so it can't be matched back to a
    # recipient.
    recipients = [
        result
        for result in sendly_client.iter_broadcast_recipients(
            batch_id=batch_id, project_id=project_id
        )
        if result.client_reference_id is not None
    ]
    broadcast = sendly_client.get_broadcast(batch_id, project_id=project_id)
    return _CampaignEngagement(recipients=recipients, broadcast=broadcast)


def _record_campaign_engagement(
    campaign_repository: CampaignRepository,
    campaign_id: UUID,
    engagement: _CampaignEngagement,
) -> None:
    for result in engagement.recipients:
        campaign_repository.record_recipient_engagement(
            campaign_id,
            result.client_reference_id,
            opened_at=result.opened_at,
            clicked_at=result.clicked_at,
        )

    broadcast = engagement.broadcast
    campaign_repository.update_campaign_engagement_counts(
        campaign_id,
        delivered_count=broadcast.delivered_count,
        bounced_count=broadcast.bounced_count,
        complained_count=broadcast.complained_count,
        opened_count=broadcast.opened_count,
        clicked_count=broadcast.clicked_count,
        synced_at=datetime.now(timezone.utc),
    )

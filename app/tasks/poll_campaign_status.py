"""Celery beat task: poll Sendly for the status of in-flight campaigns."""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.constants.campaign import CampaignStatus
from app.integrations.sendly_client_factory import build_sendly_client
from app.repositories.campaign_repository import CampaignRepository
from app.db import savepoint, session_scope

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.poll_campaign_status")
def poll_campaign_status() -> None:
    """Entry point invoked by Celery beat every 60 seconds."""
    with session_scope() as db:
        _poll_sending_campaigns(db)


def _poll_sending_campaigns(db: Session) -> None:
    """
    Check every 'sending' campaign against Sendly and mark it 'completed' once
    Sendly reports the send stage finished.

    Per docs/campaign.md, a campaign is only ever marked 'failed' when Looply
    cannot get the initial broadcast accepted/retrieved — never from polling.
    So failures here are logged and left for the next tick; a single bad
    lookup must not stop the rest of the batch, hence the per-campaign
    try/except inside the loop instead of one around the whole loop.

    Each campaign is its own phase: Sendly is queried with no database
    transaction open, then the status write runs in a savepoint and is
    committed, so one campaign's failure cannot undo another's completion.
    """
    campaign_repository = CampaignRepository(db)
    sendly_client = build_sendly_client()

    campaigns = [
        (
            campaign.id,
            campaign.batch_id,
            str(campaign.project_id) if campaign.project_id else None,
        )
        for campaign in campaign_repository.get_campaigns_by_status(
            CampaignStatus.SENDING.value
        )
    ]
    # commit: campaigns_selected. Release the read transaction before calling
    # Sendly.
    db.commit()

    for campaign_id, batch_id, project_id in campaigns:
        try:
            result = sendly_client.get_broadcast(batch_id, project_id=project_id)
            if result.finished:
                with savepoint(db):
                    campaign_repository.mark_completed(
                        campaign_id, datetime.now(timezone.utc)
                    )
                # commit: campaign_completed. Per-campaign checkpoint; also
                # releases the connection before the next Sendly call.
                db.commit()
        except Exception:
            logger.exception(
                "Failed to poll Sendly status for campaign %s (batch_id=%s)",
                campaign_id,
                batch_id,
            )

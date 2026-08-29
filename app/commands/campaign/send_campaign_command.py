"""Command to send a draft campaign through Sendly."""

import logging
import time
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session
from tessera_sdk.clients.sendly import (
    BroadcastRecipient,
    SendBroadcastRequest,
    SendlyClient,
)

from app.constants.campaign import CampaignStatus
from app.integrations.sendly_client_factory import build_sendly_client
from app.models.campaign import Campaign
from app.models.contact import Contact
from app.repositories.campaign_repository import CampaignRepository
from app.repositories.contact_list_repository import ContactListRepository

# send_broadcast is a fast accept-only call (Sendly renders/delivers
# asynchronously), and the idempotency key makes retrying the identical
# request safe, so a short manual retry loop is enough without pulling in a
# retry library.
_SEND_MAX_ATTEMPTS = 3
_SEND_RETRY_DELAY_SECONDS = 1


class SendCampaignCommand:
    """
    Command to send a draft campaign to its contact list via Sendly.

    Resolves eligible recipients, calls SendlyClient.send_broadcast(), and
    persists the resulting batch_id/status. This is the one place in the
    codebase where the command deliberately commits a partial state change
    (moving the campaign to 'failed') before re-raising, rather than only
    rolling back — 'failed' is domain-meaningful persisted state per
    docs/campaign.md, not a mid-transaction artifact.
    """

    def __init__(
        self,
        db: Session,
        sendly_client: Optional[SendlyClient] = None,
    ):
        self.db = db
        self.campaign_repository = CampaignRepository(db)
        self.contact_list_repository = ContactListRepository(db)
        self.sendly_client = (
            sendly_client if sendly_client is not None else build_sendly_client()
        )
        self.logger = logging.getLogger(__name__)
        # Set by execute() so callers (e.g. the router) can report how many
        # recipients the broadcast was actually sent to without re-querying.
        self.last_recipient_count: int = 0

    def execute(self, campaign_id: UUID) -> Campaign:
        """
        Execute the command to send a draft campaign.

        Args:
            campaign_id: The ID of the campaign to send

        Returns:
            Campaign: The updated campaign, now in 'sending' status

        Raises:
            ValueError: If the campaign is not found, not in 'draft' status,
                has no template_id, or resolves to zero eligible recipients
            Exception: If Sendly cannot accept the broadcast after retrying
        """
        campaign = self.campaign_repository.get_campaign(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        if campaign.status != CampaignStatus.DRAFT.value:
            raise ValueError(
                f"Campaign {campaign_id} is not in draft status "
                f"(current status: {campaign.status})"
            )

        if not campaign.template_id:
            raise ValueError(f"Campaign {campaign_id} has no template_id to send")

        contacts = self.contact_list_repository.get_eligible_campaign_recipients(
            campaign.contact_list_id
        )
        if not contacts:
            # Sendly's recipients field requires at least 1 entry; fail fast
            # with a clear message instead of letting the SDK raise one.
            raise ValueError(
                f"Campaign {campaign_id} has no eligible recipients "
                "(active, with an email address) in its contact list"
            )
        recipients = [self._to_broadcast_recipient(contact) for contact in contacts]
        self.last_recipient_count = len(recipients)

        request = SendBroadcastRequest(
            project_id=campaign.project_id,
            template_id=campaign.template_id,
            template_variables=campaign.template_variables,
            from_email=campaign.from_email,
            subject=campaign.subject,
            tags=[*campaign.tags, f"campaign:{str(campaign.id)[:8]}"],
            # Retrying the same campaign must never create a second broadcast.
            idempotency_key=f"campaign:{campaign.id}",
            recipients=recipients,
        )

        try:
            response = self._send_with_retry(request)
        except Exception as e:
            # mark_failed is a no-op (returns None) if a concurrent request
            # already moved this campaign out of 'draft' — that's fine, this
            # request's own attempt still failed, so still re-raise.
            self.campaign_repository.mark_failed(campaign_id)
            raise Exception(f"Failed to send campaign {campaign_id}: {str(e)}")

        updated_campaign = self.campaign_repository.mark_sending(
            campaign_id,
            response.batch_id,
            recipient_contact_ids=[contact.id for contact in contacts],
        )
        if updated_campaign is None:
            # Sendly accepted this request's broadcast, but a concurrent
            # request already transitioned the campaign out of 'draft' first.
            # Report the campaign's current persisted state rather than
            # erroring, since this attempt didn't fail on its own terms.
            updated_campaign = self.campaign_repository.get_campaign(campaign_id)
        return updated_campaign

    @staticmethod
    def _to_broadcast_recipient(contact: Contact) -> BroadcastRecipient:
        # Contact.job maps to attributes["job_title"] to match Sendly's recipient
        # contract per docs/campaign.md, since the local column is named `job`.
        return BroadcastRecipient(
            email=contact.email,
            first_name=contact.first_name,
            last_name=contact.last_name,
            attributes={
                "company": contact.company,
                "job_title": contact.job,
                "contact_type": contact.contact_type,
            },
        )

    def _send_with_retry(self, request: SendBroadcastRequest):
        last_error: Optional[Exception] = None
        for attempt in range(1, _SEND_MAX_ATTEMPTS + 1):
            try:
                return self.sendly_client.send_broadcast(request)
            except Exception as e:  # noqa: BLE001 - broad by design, retried below
                last_error = e
                self.logger.warning(
                    "send_broadcast attempt %d/%d failed for idempotency_key=%s: %s",
                    attempt,
                    _SEND_MAX_ATTEMPTS,
                    request.idempotency_key,
                    e,
                )
                if attempt < _SEND_MAX_ATTEMPTS:
                    time.sleep(_SEND_RETRY_DELAY_SECONDS * attempt)
        raise last_error

"""Command to send one test email of a draft campaign to a single contact."""

import logging
from typing import Optional
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import Session
from tessera_sdk.clients.sendly import (
    CreateEmailRequest,
    CreateEmailResponse,
    RenderRequest,
    SendlyClient,
)

from app.commands.campaign.send_campaign_command import (
    SendCampaignCommand,
    missing_send_fields,
)
from app.constants.campaign import CampaignStatus
from app.integrations.sendly_client_factory import build_sendly_client
from app.repositories.campaign_repository import CampaignRepository
from app.repositories.contact_repository import ContactRepository
from app.schemas.contact import ContactStatus

TEST_SUBJECT_PREFIX = "[TEST] "


class CampaignTestSendError(Exception):
    """Sendly did not accept the test email."""


class SendTestCampaignCommand:
    """
    Command to send one test email of a draft campaign to a single contact.

    Renders the campaign for the contact the same way a real broadcast renders
    it for each recipient, then sends the result through Sendly's single-email
    path. Nothing is written locally: the campaign stays a draft and no
    campaign recipients, batches or stats are created.
    """

    def __init__(
        self,
        db: Session,
        sendly_client: Optional[SendlyClient] = None,
    ):
        self.db = db
        self.campaign_repository = CampaignRepository(db)
        self.contact_repository = ContactRepository(db)
        self.sendly_client = (
            sendly_client if sendly_client is not None else build_sendly_client()
        )
        self.logger = logging.getLogger(__name__)

    def execute(self, campaign_id: UUID, contact_id: UUID) -> CreateEmailResponse:
        """
        Send a test email of a campaign to one contact.

        Args:
            campaign_id: The ID of the campaign to test
            contact_id: The ID of the contact to send the test email to

        Returns:
            CreateEmailResponse: What Sendly reported for the test email

        Raises:
            ValueError: If the campaign is not found, not a draft, or is missing
                content required to send; or the contact is not found, not
                active, or has no valid email address
            CampaignTestSendError: If Sendly reports the test email as failed
        """
        campaign = self.campaign_repository.get_campaign(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        # Content can only be edited while a campaign is a draft, so a test is
        # only meaningful before the campaign has been sent.
        if campaign.status != CampaignStatus.DRAFT.value:
            raise ValueError(
                f"Campaign {campaign_id} is not in draft status "
                f"(current status: {campaign.status})"
            )

        missing = missing_send_fields(campaign)
        if missing:
            raise ValueError(
                f"Campaign {campaign_id} is missing content required to send: "
                f"{', '.join(missing)}"
            )

        contact = self.contact_repository.get_contact(contact_id)
        if contact is None or contact.deleted_at is not None:
            raise ValueError(f"Contact {contact_id} not found")
        if contact.status != ContactStatus.ACTIVE.value:
            raise ValueError(f"Contact {contact_id} is not active")
        if not contact.email:
            raise ValueError(f"Contact {contact_id} has no email address")

        # Building the recipient validates the email address, so a bad address
        # fails here before anything is rendered or sent.
        try:
            recipient = SendCampaignCommand._to_broadcast_recipient(contact)
        except ValidationError as e:
            raise ValueError(
                f"Contact {contact_id} has an invalid email address"
            ) from e

        # Merge variables match what a real broadcast gives each recipient (see
        # Sendly's prepare_broadcast_chunk_task), so the test renders what the
        # audience would see.
        template_variables = {
            **(campaign.template_variables or {}),
            **(recipient.attributes or {}),
            "first_name": recipient.first_name,
        }

        # Sendly's inline single-email path does not wrap html in a layout, so
        # render the campaign with its layout first and send the result as-is.
        rendered = self.sendly_client.render(
            RenderRequest(
                html=campaign.html,
                subject=campaign.subject,
                layout_id=campaign.layout_id,
                template_variables=template_variables,
            )
        )

        try:
            request = CreateEmailRequest(
                project_id=campaign.project_id,
                from_email=campaign.from_email,
                subject=f"{TEST_SUBJECT_PREFIX}{rendered.subject}",
                html=rendered.html,
                to=[contact.email],
            )
        except ValidationError as e:
            raise ValueError(
                f"Campaign {campaign_id} has an invalid from address"
            ) from e

        response = self.sendly_client.create_email(request)
        if response.status == "failed":
            self.logger.warning(
                "Test send of campaign %s to contact %s failed: %s",
                campaign_id,
                contact_id,
                response.error_message,
            )
            raise CampaignTestSendError(
                f"Sendly could not send the test email: "
                f"{response.error_message or 'unknown error'}"
            )
        return response

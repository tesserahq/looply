"""Command to duplicate a campaign into a new draft."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.repositories.campaign_repository import CampaignRepository
from app.schemas.campaign import CampaignCreate


class DuplicateCampaignCommand:
    """
    Copy a campaign's content and audience into a new draft, so a past email
    can be reused as a starting point (this replaces starting from a Sendly
    template — see docs/prds/0007-campaign-owned-email-content.md).

    Copies what the user authored (segment, project, subject, body, layout,
    sender, variables, tags) and nothing the send produced: the copy is a
    plain 'draft' with no batch, timestamps, engagement counts, or
    recipients. Any campaign can be duplicated, whatever its status.
    """

    def __init__(self, db: Session):
        self.campaign_repository = CampaignRepository(db)

    def execute(self, campaign_id: UUID, created_by_id: UUID) -> Campaign:
        """
        Args:
            campaign_id: The campaign to copy
            created_by_id: The user creating (and owning) the copy

        Raises:
            ValueError: If the campaign is not found
        """
        source = self.campaign_repository.get_campaign(campaign_id)
        if not source:
            raise ValueError(f"Campaign {campaign_id} not found")

        duplicate = self.campaign_repository.create_campaign(
            CampaignCreate(
                name=f"Copy of {source.name}",
                segment_id=source.segment_id,
                project_id=source.project_id,
                html=source.html,
                layout_id=source.layout_id,
                subject=source.subject,
                from_email=source.from_email,
                template_variables=dict(source.template_variables or {}),
                tags=list(source.tags),
                created_by_id=created_by_id,
            )
        )

        return duplicate

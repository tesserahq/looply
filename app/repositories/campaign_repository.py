from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.campaign import Campaign
from app.constants.campaign import CampaignStatus
from app.schemas.campaign import CampaignCreate, CampaignUpdate
from app.repositories.soft_delete_repository import SoftDeleteRepository
from app.utils.db.filtering import apply_filters


class CampaignRepository(SoftDeleteRepository[Campaign]):
    """Repository class for managing campaign CRUD operations."""

    def __init__(self, db: Session):
        """
        Initialize the campaign repository.

        Args:
            db: Database session
        """
        super().__init__(db, Campaign)

    def get_campaign(self, campaign_id: UUID) -> Optional[Campaign]:
        """
        Get a single campaign by ID.

        Args:
            campaign_id: The ID of the campaign to retrieve

        Returns:
            Optional[Campaign]: The campaign or None if not found
        """
        return self.db.query(Campaign).filter(Campaign.id == campaign_id).first()

    def get_campaigns_query(self):
        """
        Get a query for all campaigns.
        This is useful for pagination with fastapi-pagination.

        Returns:
            Query: SQLAlchemy query object for campaigns
        """
        return self.db.query(Campaign).order_by(Campaign.created_at.desc())

    def get_campaigns_by_status(self, status: str) -> List[Campaign]:
        """
        Get all campaigns with a given status.

        Args:
            status: The status to filter by (e.g. CampaignStatus.SENDING)

        Returns:
            List[Campaign]: Campaigns currently in the given status
        """
        return self.db.query(Campaign).filter(Campaign.status == status).all()

    def create_campaign(self, campaign: CampaignCreate) -> Campaign:
        """
        Create a new campaign.

        Args:
            campaign: The campaign data to create

        Returns:
            Campaign: The created campaign
        """
        db_campaign = Campaign(**campaign.model_dump())
        self.db.add(db_campaign)
        self.db.commit()
        self.db.refresh(db_campaign)
        return db_campaign

    def update_campaign(
        self, campaign_id: UUID, campaign: CampaignUpdate
    ) -> Optional[Campaign]:
        """
        Update an existing campaign.

        Args:
            campaign_id: The ID of the campaign to update
            campaign: The updated campaign data

        Returns:
            Optional[Campaign]: The updated campaign or None if not found
        """
        db_campaign = self.db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if db_campaign:
            update_data = campaign.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(db_campaign, key, value)
            self.db.commit()
            self.db.refresh(db_campaign)
        return db_campaign

    def delete_campaign(self, campaign_id: UUID) -> bool:
        """
        Soft delete a campaign.

        Args:
            campaign_id: The ID of the campaign to delete

        Returns:
            bool: True if the campaign was deleted, False otherwise
        """
        return self.delete_record(campaign_id)

    def search(self, filters: dict) -> List[Campaign]:
        """
        Search campaigns based on dynamic filter criteria.

        Args:
            filters: A dictionary where keys are field names and values are either:
                - A direct value (e.g. {"status": "draft"})
                - A dictionary with 'operator' and 'value' keys (e.g. {"name": {"operator": "ilike", "value": "%launch%"}})

        Returns:
            List[Campaign]: Filtered list of campaigns matching the criteria.
        """
        query = self.db.query(Campaign)
        query = apply_filters(query, Campaign, filters)
        return query.all()

    def mark_sending(self, campaign_id: UUID, batch_id: str) -> Optional[Campaign]:
        """
        Move a campaign to 'sending' after Sendly accepts the broadcast.

        Conditioned on the campaign still being 'draft' at write time (rather
        than an unconditional update) so that two concurrent send attempts for
        the same campaign can't race: whichever request commits first wins the
        transition, and the loser's write becomes a no-op instead of
        clobbering state set by the winner.

        Args:
            campaign_id: The ID of the campaign
            batch_id: The batch ID returned by Sendly

        Returns:
            Optional[Campaign]: The updated campaign, or None if the campaign
                was no longer 'draft' when this write was attempted
        """
        updated_rows = (
            self.db.query(Campaign)
            .filter(
                Campaign.id == campaign_id,
                Campaign.status == CampaignStatus.DRAFT.value,
            )
            .update(
                {
                    Campaign.status: CampaignStatus.SENDING.value,
                    Campaign.batch_id: batch_id,
                    Campaign.sent_at: datetime.now(timezone.utc),
                },
                synchronize_session=False,
            )
        )
        self.db.commit()
        if not updated_rows:
            return None
        return self.get_campaign(campaign_id)

    def mark_completed(self, campaign_id: UUID, completed_at: datetime) -> Campaign:
        """
        Move a campaign to 'completed' once Sendly reports the send finished.

        Args:
            campaign_id: The ID of the campaign
            completed_at: When Sendly reported the send stage finished

        Returns:
            Campaign: The updated campaign
        """
        db_campaign = self.db.query(Campaign).filter(Campaign.id == campaign_id).first()
        db_campaign.status = CampaignStatus.COMPLETED.value
        db_campaign.completed_at = completed_at
        self.db.commit()
        self.db.refresh(db_campaign)
        return db_campaign

    def mark_failed(self, campaign_id: UUID) -> Optional[Campaign]:
        """
        Move a campaign to 'failed'.

        Only called when Looply cannot get the initial broadcast accepted by
        Sendly after retrying — never from later status polling (see
        docs/campaign.md "Status and results"). Conditioned on the campaign
        still being 'draft', same as mark_sending, so a losing concurrent
        request can't overwrite a status a winning request already committed
        (e.g. flipping an already-'sending' campaign back to 'failed').

        Args:
            campaign_id: The ID of the campaign

        Returns:
            Optional[Campaign]: The updated campaign, or None if the campaign
                was no longer 'draft' when this write was attempted
        """
        updated_rows = (
            self.db.query(Campaign)
            .filter(
                Campaign.id == campaign_id,
                Campaign.status == CampaignStatus.DRAFT.value,
            )
            .update(
                {Campaign.status: CampaignStatus.FAILED.value},
                synchronize_session=False,
            )
        )
        self.db.commit()
        if not updated_rows:
            return None
        return self.get_campaign(campaign_id)

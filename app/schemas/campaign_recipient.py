from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

from app.schemas.contact import ContactDetails


class CampaignRecipient(BaseModel):
    """Schema for a campaign recipient returned in API responses, with the
    recipient's current contact details joined in for display."""

    id: UUID
    """Unique identifier for the recipient record."""

    campaign_id: UUID
    """The campaign this recipient belongs to."""

    contact: ContactDetails
    """The contact that was sent to, as it currently stands (not a send-time snapshot)."""

    created_at: datetime
    """When this recipient was recorded (i.e. when the campaign was sent)."""

    model_config = {"from_attributes": True}

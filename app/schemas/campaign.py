from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime


class CampaignBase(BaseModel):
    """Base campaign model containing common campaign attributes."""

    id: Optional[UUID] = None
    """Unique identifier for the campaign. Defaults to None."""

    name: str
    """Internal name of the campaign. Required field."""

    segment_id: UUID
    """The segment defining this campaign's audience."""

    project_id: Optional[UUID] = None
    """The Sendly project that owns the template and broadcast. Optional."""

    template_id: Optional[UUID] = None
    """A live Sendly template reference. Required to send, optional while drafting."""

    template_variables: dict = {}
    """Shared variables forwarded to the Sendly template."""

    from_email: Optional[str] = None
    """Optional sender override; Sendly uses the template default when omitted."""

    subject: Optional[str] = None
    """Optional subject override; Sendly uses the template subject when omitted."""

    tags: list[str] = []
    """Tag names assigned to this campaign, forwarded to Sendly on send.
    Auto-created by name if they don't already exist - shares the same Tag
    entity as contact tags."""

    created_by_id: UUID
    """ID of the user who created this campaign."""


class CampaignCreate(CampaignBase):
    """Schema for creating a new campaign. Inherits all fields from CampaignBase."""

    pass


class CampaignCreateRequest(BaseModel):
    """Schema for creating a new campaign without created_by_id (injected from current user)."""

    name: str
    """Internal name of the campaign. Required field."""

    segment_id: UUID
    """The segment defining this campaign's audience."""

    project_id: Optional[UUID] = None
    """The Sendly project that owns the template and broadcast. Optional."""

    template_id: Optional[UUID] = None
    """A live Sendly template reference. Required to send, optional while drafting."""

    template_variables: dict = {}
    """Shared variables forwarded to the Sendly template."""

    from_email: Optional[str] = None
    """Optional sender override; Sendly uses the template default when omitted."""

    subject: Optional[str] = None
    """Optional subject override; Sendly uses the template subject when omitted."""

    tags: list[str] = []
    """Tag names assigned to this campaign, forwarded to Sendly on send.
    Auto-created by name if they don't already exist - shares the same Tag
    entity as contact tags."""


class CampaignUpdate(BaseModel):
    """Schema for updating an existing campaign. All fields are optional.

    Only allowed while the campaign is in 'draft' status (enforced by the router).
    Status transitions happen only via the send action and the status poller, never
    through this schema.
    """

    name: Optional[str] = None
    """Updated name."""

    segment_id: Optional[UUID] = None
    """Updated segment."""

    project_id: Optional[UUID] = None
    """Updated Sendly project reference."""

    template_id: Optional[UUID] = None
    """Updated Sendly template reference."""

    template_variables: Optional[dict] = None
    """Updated template variables."""

    from_email: Optional[str] = None
    """Updated sender override."""

    subject: Optional[str] = None
    """Updated subject override."""

    tags: Optional[list[str]] = None
    """Updated campaign tags."""


class CampaignInDB(CampaignBase):
    """Schema representing a campaign as stored in the database. Includes database-specific fields."""

    id: UUID
    """Unique identifier for the campaign in the database."""

    status: str
    """Campaign lifecycle status: draft, sending, completed, or failed."""

    batch_id: Optional[str] = None
    """Batch ID returned by Sendly after the broadcast is accepted."""

    sent_at: Optional[datetime] = None
    """When Sendly accepted the broadcast."""

    completed_at: Optional[datetime] = None
    """When Sendly reported the send stage finished."""

    delivered_count: int = 0
    """Number of recipients Sendly has ever reported as delivered."""

    bounced_count: int = 0
    """Number of recipients Sendly has ever reported as bounced."""

    complained_count: int = 0
    """Number of recipients Sendly has ever reported as complained."""

    opened_count: int = 0
    """Number of recipients Sendly has ever reported a first open for."""

    clicked_count: int = 0
    """Number of recipients Sendly has ever reported a first click for."""

    engagement_last_synced_at: Optional[datetime] = None
    """When engagement data was last fully refreshed from Sendly. None if no
    successful refresh has happened yet - use this, not completed_at or
    engagement_polling_expires_at, to build a "data as of" indicator."""

    engagement_polling_expires_at: Optional[datetime] = None
    """When Looply stops refreshing this campaign's engagement data. Opens
    or clicks recorded by Sendly after this point are never reflected here."""

    created_at: datetime
    """Timestamp when the campaign record was created."""

    updated_at: datetime
    """Timestamp when the campaign record was last updated."""

    model_config = {"from_attributes": True}


class Campaign(CampaignInDB):
    """Schema for campaign data returned in API responses. Inherits all fields from CampaignInDB."""

    pass


class SendCampaignResponse(BaseModel):
    """Schema for the response returned by the send campaign action."""

    id: UUID
    """Unique identifier for the campaign."""

    status: str
    """Campaign status after the send attempt (sending on success)."""

    batch_id: Optional[str] = None
    """Batch ID returned by Sendly after the broadcast is accepted."""

    recipient_count: int
    """Number of eligible, deduplicated recipients the broadcast was sent to."""

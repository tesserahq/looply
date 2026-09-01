from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CampaignStats(BaseModel):
    """Computed engagement metrics for a single campaign.

    Not persisted - computed fresh on each request from Campaign's existing
    aggregate counts and a live count of its CampaignRecipient rows. See
    docs/prds/0006-campaign-analytics.md.
    """

    recipient_count: int
    """Number of recipients the campaign was sent to (CampaignRecipient rows)."""

    delivered_count: int
    bounced_count: int
    complained_count: int
    opened_count: int
    clicked_count: int

    delivery_rate: float
    """delivered_count / recipient_count. 0.0 if recipient_count is 0."""

    bounce_rate: float
    """bounced_count / recipient_count. 0.0 if recipient_count is 0."""

    open_rate: float
    """opened_count / delivered_count. 0.0 if delivered_count is 0."""

    click_rate: float
    """clicked_count / delivered_count. 0.0 if delivered_count is 0."""

    click_to_open_rate: float
    """clicked_count / opened_count. 0.0 if opened_count is 0. Isolates
    content/CTA quality from subject-line/deliverability effects."""

    complaint_rate: float
    """complained_count / delivered_count. 0.0 if delivered_count is 0."""

    engagement_last_synced_at: Optional[datetime] = None
    """When these counts were last refreshed from Sendly. None if no
    successful sync has happened yet."""


class EngagementTimelineBucket(BaseModel):
    """Opens/clicks recorded within one elapsed-time-since-send bucket."""

    label: str
    """Human-readable bucket label, e.g. "1-4h", "3-7d"."""

    opened_count: int
    """Recipients whose first open fell in this bucket."""

    clicked_count: int
    """Recipients whose first click fell in this bucket."""


class CampaignEngagementTimeline(BaseModel):
    """Opens/clicks bucketed by time elapsed since the campaign was sent.

    Built from CampaignRecipient.opened_at/clicked_at, which are
    first-occurrence timestamps only - see docs/prds/0006-campaign-analytics.md.
    """

    buckets: list[EngagementTimelineBucket]

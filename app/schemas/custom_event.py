from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class CustomEvent(BaseModel):
    """Schema for a custom event returned in API responses. raw_envelope is
    included (not just the extracted name/occurred_at/properties) since this
    endpoint's main job is letting an operator verify integration data is flowing
    correctly (user story 11) - that requires seeing exactly what arrived on the
    wire, not just what Looply chose to extract from it.
    """

    id: UUID
    contact_id: UUID
    name: str
    occurred_at: datetime
    properties: dict
    raw_envelope: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

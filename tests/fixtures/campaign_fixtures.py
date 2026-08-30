from uuid import uuid4
import pytest
from app.constants.campaign import CampaignStatus
from app.models.campaign import Campaign


@pytest.fixture(scope="function")
def draft_campaign(db, faker, test_user, test_segment):
    """Create a draft campaign for use in tests."""
    campaign_data = {
        "name": faker.catch_phrase(),
        "status": CampaignStatus.DRAFT.value,
        "segment_id": test_segment.id,
        # The installed tessera-sdk still requires SendBroadcastRequest.project_id;
        # set it here so send-path tests exercise real request construction.
        # Once the SDK makes it optional, this can be dropped to also cover that path.
        "project_id": uuid4(),
        "template_id": uuid4(),
        "template_variables": {"greeting": "Hello"},
        "tags": ["newsletter"],
        "created_by_id": test_user.id,
    }

    campaign = Campaign(**campaign_data)
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    return campaign


@pytest.fixture(scope="function")
def sending_campaign(db, faker, test_user, test_segment):
    """Create a campaign already in 'sending' status, with a batch_id."""
    campaign_data = {
        "name": faker.catch_phrase(),
        "status": CampaignStatus.SENDING.value,
        "segment_id": test_segment.id,
        "project_id": uuid4(),
        "template_id": uuid4(),
        "batch_id": faker.uuid4(),
        "created_by_id": test_user.id,
    }

    campaign = Campaign(**campaign_data)
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    return campaign

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate

from app.db import get_db
from app.constants.campaign import CampaignStatus
from app.models.campaign import Campaign as CampaignModel
from app.schemas.campaign import (
    Campaign,
    CampaignCreate,
    CampaignCreateRequest,
    CampaignUpdate,
    SendCampaignResponse,
)
from app.schemas.campaign_recipient import CampaignRecipient as CampaignRecipientSchema
from app.repositories.campaign_repository import CampaignRepository
from app.repositories.segment_repository import SegmentRepository
from app.routers.utils.dependencies import get_campaign_by_id
from app.schemas.user import User
from tessera_sdk.server.dependencies.auth import get_current_user
from app.auth.rbac import build_rbac_dependencies
from app.commands.campaign.send_campaign_command import SendCampaignCommand

router = APIRouter(
    prefix="/campaigns",
    tags=["campaigns"],
    responses={404: {"description": "Not found"}},
)

RESOURCE = "campaign"
rbac = build_rbac_dependencies(resource=RESOURCE)


@router.post("", response_model=Campaign, status_code=status.HTTP_201_CREATED)
def create_campaign(
    campaign_data: CampaignCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _authorized: bool = Depends(rbac["create"]),
):
    """Create a new draft campaign."""
    if not SegmentRepository(db).get_segment(campaign_data.segment_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found"
        )

    campaign = CampaignCreate(
        **campaign_data.model_dump(),
        created_by_id=current_user.id,
    )

    campaign_repository = CampaignRepository(db)
    return campaign_repository.create_campaign(campaign)


@router.get("", response_model=Page[Campaign])
def list_campaigns(
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["read"]),
):
    """List all campaigns with pagination."""
    campaign_repository = CampaignRepository(db)
    return paginate(db, campaign_repository.get_campaigns_query())


@router.get("/{campaign_id}", response_model=Campaign)
def get_campaign(
    campaign: CampaignModel = Depends(get_campaign_by_id),
    _authorized: bool = Depends(rbac["read"]),
):
    """Get a campaign by ID."""
    return campaign


@router.get("/{campaign_id}/recipients", response_model=Page[CampaignRecipientSchema])
def list_campaign_recipients(
    campaign: CampaignModel = Depends(get_campaign_by_id),
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["read"]),
):
    """List the recipients a campaign was sent to, paginated.

    Empty for a campaign still in 'draft' status, since recipients are only
    recorded once the send is accepted (see mark_sending).
    """
    campaign_repository = CampaignRepository(db)
    return paginate(
        db, campaign_repository.get_recipients_by_campaign_query(campaign.id)
    )


@router.put("/{campaign_id}", response_model=Campaign)
def update_campaign(
    campaign_data: CampaignUpdate,
    existing_campaign: CampaignModel = Depends(get_campaign_by_id),
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["update"]),
):
    """Update a draft campaign. Only allowed while status is 'draft'."""
    if existing_campaign.status != CampaignStatus.DRAFT.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Campaign {existing_campaign.id} is not in draft status and cannot be updated",
        )

    return CampaignRepository(db).update_campaign(existing_campaign.id, campaign_data)


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_campaign(
    existing_campaign: CampaignModel = Depends(get_campaign_by_id),
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["delete"]),
):
    """Delete a campaign."""
    CampaignRepository(db).delete_campaign(existing_campaign.id)


@router.post(
    "/{campaign_id}/send",
    response_model=SendCampaignResponse,
    status_code=status.HTTP_200_OK,
)
def send_campaign(
    campaign: CampaignModel = Depends(get_campaign_by_id),
    db: Session = Depends(get_db),
    # Sending mutates the campaign (draft -> sending), so it's gated the same
    # as update rather than introducing a separate RBAC action for it.
    _authorized: bool = Depends(rbac["update"]),
):
    """Send a draft campaign to its segment's resolved audience via Sendly."""
    try:
        command = SendCampaignCommand(db)
        sent_campaign = command.execute(campaign.id)

        return SendCampaignResponse(
            id=sent_campaign.id,
            status=sent_campaign.status,
            batch_id=sent_campaign.batch_id,
            recipient_count=command.last_recipient_count,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send campaign: {str(e)}",
        )

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate

from app.db import get_db
from app.constants.campaign import CampaignStatus
from app.schemas.campaign import (
    Campaign,
    CampaignCreate,
    CampaignCreateRequest,
    CampaignUpdate,
    SendCampaignResponse,
)
from app.repositories.campaign_repository import CampaignRepository
from app.repositories.contact_list_repository import ContactListRepository
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
    if not ContactListRepository(db).get_contact_list(campaign_data.contact_list_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact list not found"
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
    campaign_id: UUID,
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["read"]),
):
    """Get a campaign by ID."""
    campaign = CampaignRepository(db).get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found"
        )
    return campaign


@router.put("/{campaign_id}", response_model=Campaign)
def update_campaign(
    campaign_id: UUID,
    campaign: CampaignUpdate,
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["update"]),
):
    """Update a draft campaign. Only allowed while status is 'draft'."""
    campaign_repository = CampaignRepository(db)
    existing_campaign = campaign_repository.get_campaign(campaign_id)
    if not existing_campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found"
        )
    if existing_campaign.status != CampaignStatus.DRAFT.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Campaign {campaign_id} is not in draft status and cannot be updated",
        )

    return campaign_repository.update_campaign(campaign_id, campaign)


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["delete"]),
):
    """Delete a campaign."""
    if not CampaignRepository(db).delete_campaign(campaign_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found"
        )


@router.post(
    "/{campaign_id}/send",
    response_model=SendCampaignResponse,
    status_code=status.HTTP_200_OK,
)
def send_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    # Sending mutates the campaign (draft -> sending), so it's gated the same
    # as update rather than introducing a separate RBAC action for it.
    _authorized: bool = Depends(rbac["update"]),
):
    """Send a draft campaign to its contact list via Sendly."""
    campaign_repository = CampaignRepository(db)
    campaign = campaign_repository.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign {campaign_id} not found",
        )

    try:
        command = SendCampaignCommand(db)
        sent_campaign = command.execute(campaign_id)

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

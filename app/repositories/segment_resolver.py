"""Compiles a validated segment rule tree into SQLAlchemy filters.

The rule tree's shape (app.schemas.segment_rule) is the interface; callers
never need to know how a segment resolves to SQL. Both the "resolve
contacts" query and the cheap "resolve count" variant share this one
compiled-filter code path, so a segment's preview count and its actual send
audience can never independently drift - see
docs/prds/0001-campaign-segments.md's "Segment repository/resolver" section.
"""

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Query, Session

from app.constants.campaign import CampaignStatus
from app.models.campaign import Campaign
from app.models.campaign_recipient import CampaignRecipient
from app.models.contact import Contact
from app.models.contact_list_member import ContactListMember
from app.schemas.segment_rule import (
    CampaignActivityCondition,
    CampaignActivityEvent,
    CampaignActivityOp,
    ListMembershipCondition,
    ListMembershipOp,
    LogicalOp,
    RuleGroup,
    RuleNode,
)


class SegmentResolutionError(ValueError):
    """A rule tree cannot be resolved as written.

    Raised for a campaign_activity condition whose campaign_id doesn't
    reference an existing, completed campaign - at segment create/update
    time this maps to a 422; at resolve time (preview or send) it must
    surface as an explicit error rather than silently widening the
    audience (see docs/prds/0001-campaign-segments.md's "Known Risks").
    """


def validate_campaign_references(db: Session, root: RuleNode) -> None:
    """Walk a rule tree and raise if any campaign_activity leaf is dangling.

    Called both at segment create/update time and again at resolution time
    (via _campaign_activity_clause), since a campaign referenced by an
    already-saved segment can be deleted or reverted afterward.
    """
    if isinstance(root, RuleGroup):
        for child in root.conditions:
            validate_campaign_references(db, child)
    elif isinstance(root, CampaignActivityCondition):
        _require_completed_campaign(db, root.campaign_id)


def _require_completed_campaign(db: Session, campaign_id) -> None:
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if campaign is None or campaign.status != CampaignStatus.COMPLETED.value:
        raise SegmentResolutionError(
            f"campaign_activity references campaign {campaign_id}, which "
            "does not exist or is not completed"
        )


def _list_membership_clause(condition: ListMembershipCondition):
    member_exists = (
        select(ContactListMember.id)
        .where(
            ContactListMember.contact_id == Contact.id,
            ContactListMember.contact_list_id == condition.list_id,
            ContactListMember.deleted_at.is_(None),
        )
        .exists()
    )
    if condition.op == ListMembershipOp.IN:
        return member_exists
    return ~member_exists


def _campaign_activity_clause(db: Session, condition: CampaignActivityCondition):
    _require_completed_campaign(db, condition.campaign_id)

    timestamp_column = (
        CampaignRecipient.opened_at
        if condition.event == CampaignActivityEvent.OPENED
        else CampaignRecipient.clicked_at
    )
    was_sent = select(CampaignRecipient.id).where(
        CampaignRecipient.contact_id == Contact.id,
        CampaignRecipient.campaign_id == condition.campaign_id,
    )
    if condition.op == CampaignActivityOp.HAS:
        return was_sent.where(timestamp_column.isnot(None)).exists()
    # HAS_NOT means "was sent this campaign and did not open/click it" - a
    # contact never sent this campaign (no CampaignRecipient row at all)
    # does not qualify, so this still requires `was_sent`, just with the
    # timestamp null instead of dropping the EXISTS entirely.
    return was_sent.where(timestamp_column.is_(None)).exists()


def _compile(db: Session, node: RuleNode):
    if isinstance(node, RuleGroup):
        clauses = [_compile(db, child) for child in node.conditions]
        return and_(*clauses) if node.op == LogicalOp.AND else or_(*clauses)
    if isinstance(node, ListMembershipCondition):
        return _list_membership_clause(node)
    if isinstance(node, CampaignActivityCondition):
        return _campaign_activity_clause(db, node)
    raise TypeError(f"Unknown rule node type: {type(node)!r}")  # pragma: no cover


def resolve_contacts_query(db: Session, root: RuleNode) -> Query:
    """Compile a validated rule tree into a Contact query.

    Raises:
        SegmentResolutionError: a campaign_activity condition references a
            campaign that no longer exists or isn't completed.
    """
    return db.query(Contact).filter(_compile(db, root))


def resolve_count(db: Session, root: RuleNode) -> int:
    """Cheap COUNT(*) variant of resolve_contacts_query - never persisted."""
    return db.query(func.count(Contact.id)).filter(_compile(db, root)).scalar()

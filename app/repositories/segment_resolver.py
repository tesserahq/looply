"""Compiles a validated segment rule tree into SQLAlchemy filters.

The rule tree's shape (app.schemas.segment_rule) is the interface; callers
never need to know how a segment resolves to SQL. Both the "resolve
contacts" query and the cheap "resolve count" variant share this one
compiled-filter code path, so a segment's preview count and its actual send
audience can never independently drift - see
docs/prds/0001-campaign-segments.md's "Segment repository/resolver" section.
"""

from sqlalchemy import Boolean, Date, Numeric, Text, and_, func, or_, select
from sqlalchemy.orm import Query, Session

from app.constants.campaign import CampaignStatus
from app.models.campaign import Campaign
from app.models.campaign_recipient import CampaignRecipient
from app.models.contact import Contact
from app.models.contact_custom_field_value import ContactCustomFieldValue
from app.models.contact_list_member import ContactListMember
from app.models.contact_tag import ContactTag
from app.models.custom_field_definition import CustomFieldDefinition
from app.schemas.custom_field_definition import FieldValueType
from app.schemas.segment_rule import (
    CampaignActivityCondition,
    CampaignActivityEvent,
    CampaignActivityOp,
    ContactFieldCondition,
    ContactFieldOp,
    CustomFieldCondition,
    ListMembershipCondition,
    ListMembershipOp,
    LogicalOp,
    RuleGroup,
    RuleNode,
    TagMembershipCondition,
    TagMembershipOp,
)
from app.utils.db.filtering import OPERATORS

# custom_field's equivalent of segment_rule.ALLOWED_OPS_BY_FIELD - keyed by
# FieldValueType instead of a fixed field name, since custom_field's "field"
# is dynamic (a CustomFieldDefinition row looked up at resolve time), this is
# the one place the allow-list can live.
ALLOWED_OPS_BY_VALUE_TYPE: dict[FieldValueType, frozenset[ContactFieldOp]] = {
    FieldValueType.STRING: frozenset(
        {ContactFieldOp.EQ, ContactFieldOp.NEQ, ContactFieldOp.ILIKE, ContactFieldOp.IN}
    ),
    FieldValueType.NUMBER: frozenset(
        {
            ContactFieldOp.EQ,
            ContactFieldOp.NEQ,
            ContactFieldOp.GT,
            ContactFieldOp.GTE,
            ContactFieldOp.LT,
            ContactFieldOp.LTE,
            ContactFieldOp.IN,
        }
    ),
    FieldValueType.BOOLEAN: frozenset({ContactFieldOp.EQ, ContactFieldOp.NEQ}),
    FieldValueType.DATE: frozenset(
        {
            ContactFieldOp.EQ,
            ContactFieldOp.NEQ,
            ContactFieldOp.GT,
            ContactFieldOp.GTE,
            ContactFieldOp.LT,
            ContactFieldOp.LTE,
        }
    ),
}


# ContactCustomFieldValue.value is JSONB, storing different Python types
# depending on the definition's value_type - apply_filters'/OPERATORS' plain
# `column > value` (fine for contact_field's ordinary typed columns) doesn't
# work directly against a JSONB column. `astext` only applies after a path/key
# index (col['key'].astext); for a whole-document scalar we extract the text
# via the `#>>'{}'` operator instead, then cast to the right SQL type per
# value_type before applying an operator.
def _as_text(col):
    return col.op("#>>", return_type=Text)("{}")


CAST_BY_VALUE_TYPE = {
    FieldValueType.STRING: _as_text,
    FieldValueType.NUMBER: lambda col: _as_text(col).cast(Numeric),
    FieldValueType.BOOLEAN: lambda col: _as_text(col).cast(Boolean),
    FieldValueType.DATE: lambda col: _as_text(col).cast(Date),
}


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


def validate_custom_field_references(db: Session, root: RuleNode) -> None:
    """Walk a rule tree and raise if any custom_field leaf references an
    undefined field or an operator its value_type doesn't allow.

    Called both at segment create/update time and again at resolution time
    (via _custom_field_clause), since a definition referenced by an
    already-saved segment can be soft-deleted afterward.
    """
    if isinstance(root, RuleGroup):
        for child in root.conditions:
            validate_custom_field_references(db, child)
    elif isinstance(root, CustomFieldCondition):
        _require_compatible_custom_field(db, root.field_name, root.operator)


def _require_compatible_custom_field(
    db: Session, field_name: str, operator: ContactFieldOp
) -> CustomFieldDefinition:
    definition = (
        db.query(CustomFieldDefinition)
        .filter(func.lower(CustomFieldDefinition.name) == field_name.lower())
        .first()
    )
    if definition is None:
        raise SegmentResolutionError(
            f"custom_field references field {field_name!r}, which does not exist"
        )
    value_type = FieldValueType(definition.value_type)
    if operator not in ALLOWED_OPS_BY_VALUE_TYPE[value_type]:
        raise SegmentResolutionError(
            f"operator {operator} not allowed for custom field {field_name!r} "
            f"(value_type={value_type.value})"
        )
    return definition


def _require_completed_campaign(db: Session, campaign_id) -> None:
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if campaign is None or campaign.status != CampaignStatus.COMPLETED.value:
        raise SegmentResolutionError(
            f"campaign_activity references campaign {campaign_id}, which "
            "does not exist or is not completed"
        )


def collect_tag_ids(root: RuleNode) -> set:
    """All tag_ids referenced anywhere in a rule tree's tags leaves.

    Used to warn before deleting a tag that a saved segment still filters
    on - see app.routers.tag's GET /tags/{tag_id}/usage.
    """
    if isinstance(root, RuleGroup):
        ids: set = set()
        for child in root.conditions:
            ids |= collect_tag_ids(child)
        return ids
    if isinstance(root, TagMembershipCondition):
        return set(root.tag_ids)
    return set()


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


def _tag_membership_clause(condition: TagMembershipCondition):
    member_exists = (
        select(ContactTag.id)
        .where(
            ContactTag.contact_id == Contact.id,
            ContactTag.tag_id.in_(condition.tag_ids),
        )
        .exists()
    )
    if condition.op == TagMembershipOp.IN:
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
    has_opened_or_clicked = was_sent.where(timestamp_column.isnot(None)).exists()
    if condition.op == CampaignActivityOp.HAS:
        return has_opened_or_clicked
    # HAS_NOT is a true negation over the whole contact set: it includes
    # contacts who were sent the campaign but didn't open/click it, AND
    # contacts never sent the campaign at all (no CampaignRecipient row).
    # Segments filter down from "all contacts", so a rule must never
    # implicitly narrow that universe on its own.
    return ~has_opened_or_clicked


def _contact_field_clause(condition: ContactFieldCondition):
    # field/operator/value-type were already fully validated by
    # ContactFieldCondition itself (see app.schemas.segment_rule) - no DB
    # lookup needed, unlike custom_field below.
    column = getattr(Contact, condition.field.value)
    op_func = OPERATORS[condition.operator.value]
    return op_func(column, condition.value)


def _custom_field_clause(db: Session, condition: CustomFieldCondition):
    definition = _require_compatible_custom_field(
        db, condition.field_name, condition.operator
    )
    value_type = FieldValueType(definition.value_type)
    cast_value_column = CAST_BY_VALUE_TYPE[value_type](ContactCustomFieldValue.value)
    op_func = OPERATORS[condition.operator.value]

    match_exists = select(ContactCustomFieldValue.id).where(
        ContactCustomFieldValue.contact_id == Contact.id,
        ContactCustomFieldValue.field_definition_id == definition.id,
        op_func(cast_value_column, condition.value),
    )
    return match_exists.exists()


def _compile(db: Session, node: RuleNode):
    if isinstance(node, RuleGroup):
        clauses = [_compile(db, child) for child in node.conditions]
        return and_(*clauses) if node.op == LogicalOp.AND else or_(*clauses)
    if isinstance(node, ListMembershipCondition):
        return _list_membership_clause(node)
    if isinstance(node, CampaignActivityCondition):
        return _campaign_activity_clause(db, node)
    if isinstance(node, ContactFieldCondition):
        return _contact_field_clause(node)
    if isinstance(node, CustomFieldCondition):
        return _custom_field_clause(db, node)
    if isinstance(node, TagMembershipCondition):
        return _tag_membership_clause(node)
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

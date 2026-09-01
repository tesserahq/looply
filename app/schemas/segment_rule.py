"""Segment rule tree: a discriminated, depth/size-bounded Pydantic schema.

Not raw/free-form JSON - the API rejects (422) anything that doesn't parse
into this shape. Every operator, event name, and condition-type discriminator
is a named constant (a str Enum member), never a bare string literal, so a
typo is caught before a request is ever sent and the resolver
(app/repositories/segment_resolver.py) can switch/match on these enum members
rather than re-typing spellings by hand.

See docs/prds/0001-campaign-segments.md's "Rule tree schema" section for the
full design rationale, including the resource-exhaustion risk these limits
close.
"""

from enum import Enum
from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.contact import ContactStatus, ContactType

MAX_TREE_DEPTH = 5
"""A RuleGroup nested inside a RuleGroup counts as +1 depth."""

MAX_LEAVES = 25
"""Total leaf conditions anywhere in the tree."""

MAX_IN_VALUES = 100
"""Max items in an "in" value list (contact_field/custom_field)."""

MAX_STRING_LENGTH = 255
"""Max length of any string leaf value."""


class ConditionType(str, Enum):
    LIST_MEMBERSHIP = "list_membership"
    CAMPAIGN_ACTIVITY = "campaign_activity"
    CONTACT_FIELD = "contact_field"
    CUSTOM_FIELD = "custom_field"
    TAGS = "tags"


class LogicalOp(str, Enum):
    AND = "and"
    OR = "or"


class ListMembershipOp(str, Enum):
    IN = "in"
    NOT_IN = "not_in"


class CampaignActivityEvent(str, Enum):
    OPENED = "opened"
    CLICKED = "clicked"


class CampaignActivityOp(str, Enum):
    HAS = "has"
    HAS_NOT = "has_not"


class ListMembershipCondition(BaseModel):
    type: Literal[ConditionType.LIST_MEMBERSHIP] = ConditionType.LIST_MEMBERSHIP
    list_id: UUID
    op: ListMembershipOp


class CampaignActivityCondition(BaseModel):
    type: Literal[ConditionType.CAMPAIGN_ACTIVITY] = ConditionType.CAMPAIGN_ACTIVITY
    campaign_id: UUID
    event: CampaignActivityEvent
    op: CampaignActivityOp


class TagMembershipOp(str, Enum):
    IN = "in"
    NOT_IN = "not_in"


class TagMembershipCondition(BaseModel):
    """Matches a contact against a set of tags with ANY-of (OR) semantics:
    IN means "has at least one of tag_ids", NOT_IN means "has none of
    tag_ids". ALL-of-multiple-tags is expressible by nesting multiple
    single-tag IN conditions under an AND RuleGroup instead of a separate
    match-mode field here.

    No tag existence is validated here or at resolve time (same as
    list_membership's list_id) - a tag_id that no longer exists just never
    matches, it doesn't error the segment.
    """

    type: Literal[ConditionType.TAGS] = ConditionType.TAGS
    tag_ids: list[UUID] = Field(min_length=1, max_length=MAX_IN_VALUES)
    op: TagMembershipOp


class ContactFieldName(str, Enum):
    CONTACT_TYPE = "contact_type"
    COMPANY = "company"
    CITY = "city"
    STATE = "state"
    COUNTRY = "country"
    STATUS = "status"


class ContactFieldOp(str, Enum):
    EQ = "=="
    NEQ = "!="
    ILIKE = "ilike"
    IN = "in"
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="


# GT/GTE/LT/LTE exist on this shared enum for custom_field's NUMBER/DATE values
# (e.g. `family_member_count >= 3`) - none of contact_field's own columns are
# ordered/numeric, so none of them grant these ops below (see
# ALLOWED_OPS_BY_FIELD). Kept as one shared enum, rather than a second
# near-duplicate one, so both leaf types reuse the same apply_filters
# (app/utils/db/filtering.py) comparison logic.
STRING_FIELD_OPS = frozenset(
    {ContactFieldOp.EQ, ContactFieldOp.NEQ, ContactFieldOp.ILIKE, ContactFieldOp.IN}
)

# status is a fixed enum (ContactStatus), not free text - ILIKE doesn't apply,
# but IN is genuinely useful (e.g. "active or pending" for a re-engagement
# segment) so it gets EQ/NEQ/IN rather than reusing STRING_FIELD_OPS wholesale.
STATUS_FIELD_OPS = frozenset({ContactFieldOp.EQ, ContactFieldOp.NEQ, ContactFieldOp.IN})

# Deliberately an explicit per-field allow-list, not `frozenset(ContactFieldOp)` -
# so a future operator added to the shared enum doesn't silently become
# available on every existing field just by existing on the enum.
ALLOWED_OPS_BY_FIELD: dict[ContactFieldName, frozenset[ContactFieldOp]] = {
    ContactFieldName.CONTACT_TYPE: STRING_FIELD_OPS,
    ContactFieldName.COMPANY: STRING_FIELD_OPS,
    ContactFieldName.CITY: STRING_FIELD_OPS,
    ContactFieldName.STATE: STRING_FIELD_OPS,
    ContactFieldName.COUNTRY: STRING_FIELD_OPS,
    ContactFieldName.STATUS: STATUS_FIELD_OPS,
}


class ContactFieldCondition(BaseModel):
    """Filters on an existing Contact column. field is restricted to a fixed
    allow-list of columns; operator is restricted per-field by
    ALLOWED_OPS_BY_FIELD - both are static, so (unlike custom_field below) this
    condition is fully validated here, no DB lookup needed.
    """

    type: Literal[ConditionType.CONTACT_FIELD] = ConditionType.CONTACT_FIELD
    field: ContactFieldName
    operator: ContactFieldOp
    value: Union[str, list[str]]

    @model_validator(mode="after")
    def enforce_field_op_and_value_type(self) -> "ContactFieldCondition":
        if self.operator not in ALLOWED_OPS_BY_FIELD[self.field]:
            raise ValueError(
                f"operator {self.operator} not allowed for field {self.field}"
            )
        if self.operator is ContactFieldOp.IN and not isinstance(self.value, list):
            raise ValueError("in requires a list value")
        if self.field is ContactFieldName.CONTACT_TYPE:
            values = self.value if isinstance(self.value, list) else [self.value]
            if not all(v in set(ContactType) for v in values):
                raise ValueError("contact_type value must be a known ContactType")
        if self.field is ContactFieldName.STATUS:
            values = self.value if isinstance(self.value, list) else [self.value]
            if not all(v in set(ContactStatus) for v in values):
                raise ValueError("status value must be a known ContactStatus")
        values = self.value if isinstance(self.value, list) else [self.value]
        if len(values) > MAX_IN_VALUES:
            raise ValueError(f"value list exceeds max {MAX_IN_VALUES} items")
        for v in values:
            if isinstance(v, str) and len(v) > MAX_STRING_LENGTH:
                raise ValueError(f"string value exceeds max length {MAX_STRING_LENGTH}")
        return self


class CustomFieldCondition(BaseModel):
    """Filters on a ContactCustomFieldValue by field_name. Unlike
    contact_field, field_name is a free-form string resolved against a
    CustomFieldDefinition row at request time - its value_type isn't known
    until that row is looked up, so operator/value-type compatibility can't be
    fully validated here. This model only bounds string/list length; the
    resolver (app/repositories/segment_resolver.py) does the
    field-exists + operator-matches-value_type validation via a DB lookup,
    both at segment create/update and again at resolution time.
    """

    type: Literal[ConditionType.CUSTOM_FIELD] = ConditionType.CUSTOM_FIELD
    field_name: str
    operator: ContactFieldOp
    value: Union[str, float, bool]

    @model_validator(mode="after")
    def enforce_string_length(self) -> "CustomFieldCondition":
        if isinstance(self.value, str) and len(self.value) > MAX_STRING_LENGTH:
            raise ValueError(f"string value exceeds max length {MAX_STRING_LENGTH}")
        return self


Leaf = Annotated[
    Union[
        ListMembershipCondition,
        CampaignActivityCondition,
        ContactFieldCondition,
        CustomFieldCondition,
        TagMembershipCondition,
    ],
    Field(discriminator="type"),
]


class RuleGroup(BaseModel):
    op: LogicalOp
    conditions: list["RuleNode"] = Field(min_length=1, max_length=MAX_LEAVES)


# RuleGroup has no discriminator field of its own: a node is a RuleGroup if
# it has "op"+"conditions", else it's validated against the Leaf union by
# its "type" field. Pydantic's smart-union mode resolves this without an
# explicit discriminator on the outer union.
RuleNode = Union[RuleGroup, Leaf]
RuleGroup.model_rebuild()


def _measure(node: "RuleNode") -> tuple[int, int]:
    """Return (depth, leaf_count) for a validated RuleNode tree.

    A bare leaf has depth 0; each level of RuleGroup nesting adds 1, so
    MAX_TREE_DEPTH bounds how many groups can be nested inside each other,
    independent of how many leaves sit at any one level.
    """
    if isinstance(node, RuleGroup):
        child_measurements = [_measure(child) for child in node.conditions]
        depth = 1 + max((d for d, _ in child_measurements), default=0)
        leaf_count = sum(n for _, n in child_measurements)
        return depth, leaf_count
    return 0, 1


class SegmentRuleCreate(BaseModel):
    """The full validated payload stored (as JSON) in Segment.rule."""

    root: RuleNode

    @model_validator(mode="after")
    def enforce_limits(self) -> "SegmentRuleCreate":
        depth, leaves = _measure(self.root)
        if depth > MAX_TREE_DEPTH:
            raise ValueError(f"rule tree exceeds max depth {MAX_TREE_DEPTH}")
        if leaves > MAX_LEAVES:
            raise ValueError(f"rule tree exceeds max {MAX_LEAVES} leaf conditions")
        return self

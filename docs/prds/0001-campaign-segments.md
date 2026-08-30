# Campaign Segments (Exclude Prior-Campaign Openers/Clickers)

## Problem Statement

A user sends a campaign to a contact list — say, 20 people. Sendly (the sending provider) tracks
who opened or clicked each email, but Looply never sees or stores that data; the campaign just
flips to `completed`. If only 5 of the 20 engaged, the user has no way to build a follow-up
campaign to the other 15 without manually cross-referencing Sendly's dashboard and hand-picking
contacts — Looply campaigns can only target one whole contact list, with no way to narrow or
exclude.

More generally, the user has no way to target a campaign at anything more specific than "everyone
currently in this list." Segmenting by past engagement (opened/didn't open a prior campaign) or by
contact attributes (company, contact type, location) isn't possible today.

## Solution

Introduce **Segments**: a saved, reusable, rule-based filter over Looply's contact base as a
whole — the way Loops.so scopes a Segment to its entire Audience rather than to one sub-list. A
segment is not owned by, or scoped to, any single contact list; instead, "is a member of list X"
is just one filterable condition among others (company, contact type, location, prior-campaign
engagement), combinable with AND/OR logic. A campaign's audience is defined entirely by the
segment it references — there is no separate, required "base list" a segment narrows down.

This is a deliberate reversal of an earlier version of this PRD, which scoped every segment to
exactly one contact list (matching Mailchimp's Audience-scoped segments). That shape forced a
rigid two-step flow — create a list, then a segment on top of it — and made a segment unusable
outside the list it was born under. Contacts already support many-to-many list membership
(`ContactListMember`), so there's no structural reason to also force a hard 1:1 between a segment
and a list; list membership fits naturally as just another condition type.

This requires Looply to start caching a thin slice of engagement data it deliberately doesn't
store today: `opened_at`/`clicked_at` per recipient, and campaign-level result counts, refreshed by
polling Sendly for a bounded window after a campaign completes. This is a conscious, scoped
reversal of the rule in `docs/campaign.md` that Looply must not duplicate Sendly's delivery-event
data — that document must be updated alongside this work, not left contradicting the code.

The work is split into phases so each lands as an independently shippable, coherent slice rather
than one large change. Phase 1 depends on `tessera-sdk` support for the new count fields and
per-email listing, which has already been merged and is available today — see "Implementation
Decisions."

## User Stories

1. As a campaign sender, I want to see how many recipients opened, clicked, bounced, or complained
   about a completed campaign, so that I know whether it worked without leaving Looply.
2. As a campaign sender, I want that engagement data to keep updating for a few days after the
   campaign completes, so that a report I check the day after isn't stuck showing zero opens.
3. As a campaign sender, I want to create a segment that excludes contacts who opened a specific
   prior campaign, so that I can send a follow-up only to people who haven't engaged yet.
4. As a campaign sender, I want to create a segment that targets only contacts who *did* open or
   click a specific prior campaign, so that I can send a reward/upsell campaign to my most engaged
   audience.
5. As a campaign sender, I want to filter a segment by contact fields like company, contact type,
   or location, so that I can combine engagement history with who the contact actually is.
6. As a campaign sender, I want to filter a segment by list membership (in a list, or not in a
   list), so that "everyone in list X" is just as expressible as any other condition, without a
   list being a required, separate concept from the segment itself.
7. As a campaign sender, I want to combine multiple conditions — including list membership,
   engagement, and contact fields — with AND/OR logic, so that I can express rules like "in list X
   AND in Company Y AND did not open Campaign A."
8. As a campaign sender, I want to save a segment with a name and reuse it across multiple
   campaigns regardless of which lists it happens to touch, so that I don't have to rebuild the
   same filter every time I send a related follow-up.
9. As a campaign sender, I want a campaign's audience to be defined by a single required segment,
   so that building a campaign is always "choose or build a segment," not two separate steps of
   picking a list and then optionally narrowing it.
10. As a campaign sender, when all I want is "everyone in this list," I want that to still be as
    quick as picking a list, so that the segment model being more general doesn't make the common
    case more work.
11. As a campaign sender, I want the segment's conditions to be evaluated at send time (same moment
    today's active/has-email eligibility check runs), so that the audience reflects the latest
    cached engagement data available when I actually send.
12. As a campaign sender, I want to understand that engagement caching has a bounded window (not
    indefinite), so that I'm not surprised if someone who opens after that window still receives a
    follow-up campaign meant to exclude them.
13. As a developer maintaining Looply, I want the engagement cache to be a narrow, clearly-scoped
    addition (timestamps only, not a full event log), so that Looply's stated boundary with Sendly
    stays intentional and legible rather than silently eroding.
14. As a developer maintaining Looply, I want the segment rule tree to be evaluated by compiling it
    into SQLAlchemy filters against local tables, so that resolving a segment's audience is a single
    local query, not a live call out to Sendly on every campaign build or send.
15. As a campaign sender, I want to see how many contacts a segment currently resolves to — while
    still editing it, before saving — so that I get a warning if a rule tree I built (especially one
    with no `list_membership` condition) is about to target a much bigger audience than I intended.

## Implementation Decisions

### Phase 1 — Engagement cache + campaign result counts (no segments yet)

Depends on `tessera-sdk`'s `SendlyClient` exposing the count fields (`delivered_count`,
`bounced_count`, `complained_count`, `opened_count`) on `GetBroadcastResponse` and a per-email
method (e.g. `list_emails(batch_id)`, wrapping Sendly's `GET /emails?batch_id=...`) returning each
recipient's email plus `opened_at`/`clicked_at`. That SDK work has already been merged and is
available in `tessera-sdk` today, so Phase 1 is unblocked and can start immediately.

Ships a visible, standalone improvement (user story 1–2) and builds the data foundation everything
else depends on. Nothing in this phase depends on the segment redesign below — it's unaffected by
whether segments end up list-scoped or not.

- **Schema**: add `opened_at: datetime | None` and `clicked_at: datetime | None` to
  `CampaignRecipient` (`app/models/campaign_recipient.py`). Deliberately narrow — timestamps only,
  first-occurrence semantics, not a per-event log. This is the one piece of "delivery event" data
  Looply will now own; `docs/campaign.md` gets updated in this phase to describe it honestly as a
  scoped exception rather than leaving the "must not duplicate" line contradicted by the code.
- **Schema**: add result-count columns to `Campaign` (`delivered_count`, `bounced_count`,
  `complained_count`, `opened_count`, `clicked_count`) — currently nothing is stored; today's
  `poll_campaign_status` task only reads `finished` to flip status, then discards the rest of the
  response.
- **Send-flow change** (prerequisite for the task below): `_to_broadcast_recipient` in
  `app/commands/campaign/send_campaign_command.py` must set `client_reference_id` on each
  `BroadcastRecipient` (e.g. to `contact.id`) when building the broadcast send. This costs nothing
  at send time and is what makes the polling task below able to match results back to a contact
  without relying on the (mutable) email address — see "Known Risks" for why matching by email is
  unsafe.
- **New background task**, following the existing `poll_campaign_status` pattern
  (`app/tasks/poll_campaign_status.py`, same `build_sendly_client()` + per-item try/except so one
  bad lookup doesn't stop the batch): for each `completed` campaign still inside its polling
  window, call the SDK's `iter_broadcast_recipients(batch_id=batch_id)` (not
  `list_broadcast_recipients()` — the plain method returns only a single page; the iterator
  transparently walks every page so campaigns with more than 50 recipients aren't silently
  truncated) and, for each `BroadcastRecipientResult`, match its `client_reference_id` back to the
  corresponding `CampaignRecipient`/`Contact` and update `opened_at`/`clicked_at`. Also call
  `get_broadcast()` to refresh the campaign's result counts.
- **Polling window**: a fixed, globally-configured duration (e.g. via app settings, defaulting to
  3 days) after `completed_at`, after which the task stops polling that campaign. Per-campaign
  override is explicitly out of scope for Phase 1 (see "Out of Scope") — global config only, to
  keep the first slice small.
- **Known accepted limitation**: engagement after the window closes is never reflected. A contact
  who opens on day 5 (window = 3 days) still shows as a non-opener in Looply's cache indefinitely.
  This must be visible to the user in the product (e.g. a "data as of" indicator on results), not
  just documented here — exact UI treatment is deferred to whichever phase defines the results UI.
- No API/router changes are strictly required for Phase 1 beyond exposing the new count fields on
  the existing campaign read schema/endpoint (`app/schemas/campaign.py`,
  `app/routers/campaign.py`) — no new endpoints.

### Phase 2 — `Segment` model, rule engine, and campaign send-time wiring (list membership + campaign-activity conditions)

Ships the ability to build and save a list-agnostic segment based on list membership and
prior-campaign engagement, **and** wires it end-to-end into campaign sending (user stories 3–4,
6–11), so the original problem ("exclude prior openers") is fully solvable by the end of this
phase — not just modeled. `contact_field` conditions are deliberately deferred to Phase 3; every
other piece needed to build a segment, attach it to a campaign, and send to it ships here.

This absorbs what an earlier version of this PRD placed in Phase 3: the `Campaign.contact_list_id`
→ `Campaign.segment_id` schema cutover and the send-flow's switch to segment resolution. That move
was made deliberately, per design review — see "Known Risks" (now resolved) for why leaving segment
resolution to Phase 3 while Phase 2 claimed to already solve the user problem was a real
contradiction, not just a wording issue.

- **New model** `Segment` (new file, e.g. `app/models/segment.py`), following existing model
  conventions (`TimestampMixin`, `SoftDeleteMixin`, UUID PK, `created_by_id` FK to `users`):
  - `name: str` (unique per account/workspace, not per-list — segments are no longer namespaced
    under a list)
  - `rule: JSONB` — the condition tree (see "Rule tree" below)
  - `created_by_id: UUID` (FK to `users.id`)
  - Deliberately **no** `contact_list_id` column. A segment has no owning list; any relationship to
    a list exists only inside its rule tree, as a `list_membership` condition.
- **Rule tree schema**: discriminated Pydantic models, not raw/free-form JSON — the API rejects
  (HTTP 422) anything that doesn't parse into this shape, closing the resource-exhaustion surface
  identified in "Known Risks" below. `Segment.rule` (JSONB) stores the validated tree's
  `model_dump(mode="json")`.

  Every operator, event name, and condition-type discriminator is a named constant (a `str, Enum`
  member), never a bare string literal — both so a typo is a Python `NameError`/import failure
  caught before a request is ever sent, not a silently-accepted-then-ignored value, and so
  `app/utils/db/filtering.py`'s resolver code and any future condition type share one canonical
  set of spellings instead of each call site re-typing `"not_in"` by hand.

  ```python
  MAX_TREE_DEPTH = 5       # a RuleGroup nested inside a RuleGroup counts as +1 depth
  MAX_LEAVES = 25          # total leaf conditions anywhere in the tree
  MAX_IN_VALUES = 100      # max items in a contact_field "in" value list (Phase 3)
  MAX_STRING_LENGTH = 255  # max length of any string leaf value

  class ConditionType(str, Enum):
      LIST_MEMBERSHIP = "list_membership"
      CAMPAIGN_ACTIVITY = "campaign_activity"
      CONTACT_FIELD = "contact_field"       # Phase 3

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

  Leaf = Annotated[
      Union[ListMembershipCondition, CampaignActivityCondition],
      Field(discriminator="type"),
  ]

  class RuleGroup(BaseModel):
      op: LogicalOp
      conditions: list["RuleNode"] = Field(min_length=1, max_length=MAX_LEAVES)

  RuleNode = Union[RuleGroup, Leaf]  # RuleGroup has no discriminator field of its own;
                                     # a node is a RuleGroup if it has "op"+"conditions",
                                     # else validated against the Leaf union by "type"
  RuleGroup.model_rebuild()

  class SegmentRuleCreate(BaseModel):
      root: RuleNode

      @model_validator(mode="after")
      def enforce_limits(self) -> "SegmentRuleCreate":
          depth, leaves = _measure(self.root)  # walks the tree once
          if depth > MAX_TREE_DEPTH:
              raise ValueError(f"rule tree exceeds max depth {MAX_TREE_DEPTH}")
          if leaves > MAX_LEAVES:
              raise ValueError(f"rule tree exceeds max {MAX_LEAVES} leaf conditions")
          return self
  ```

  Same rule applies going forward: Phase 3's `contact_field` condition must define
  `ContactFieldName` and `ContactFieldOp` enums (mirroring the allow-lists below) rather than
  typing `"contact_type"`/`"=="` as raw strings at each call site, and the resolver
  (`app/repositories/segment_repository.py` or wherever it lands) must switch/match on these enum
  members — never on the raw string values — so a new operator can't be introduced by silently
  falling through to `apply_filters`'s permissive default.

  Phase 2 supports exactly the two leaf types above:
  - `list_membership` — resolved as a join against `ContactListMember` filtered to the given
    `list_id`, checking `deleted_at IS NULL` for `ListMembershipOp.IN` (or its absence for
    `ListMembershipOp.NOT_IN`). This is what makes "everyone in list X" expressible without a
    segment needing a dedicated list-scope column.
  - `campaign_activity` — resolved as a join against `CampaignRecipient` filtered to the given
    `campaign_id`, checking whether the relevant timestamp column is set (see "Known Risks" for
    the `CampaignActivityOp.HAS_NOT` semantics this must define precisely, and the lifecycle
    validation `campaign_id` needs).
  - A rule tree with **zero** `list_membership` conditions is valid and resolves against the
    account's entire contact base — see "Out of Scope" for why this is intentionally unguarded.
  - Phase 3b's `contact_field` condition slots into the same `Leaf` union as a third member, with
    its own field/operator/value-type allow-list (see Phase 3b below) rather than accepting
    `apply_filters`'s permissive fallback — `ContactFieldOp` restricted per-field by
    `ALLOWED_OPS_BY_FIELD`, `ContactFieldName` restricted to the named `Contact` columns, string
    values capped at `MAX_STRING_LENGTH`, `in` lists capped at `MAX_IN_VALUES`.
  - **`campaign_activity.campaign_id` lifecycle validation**: on segment create/update, the
    referenced campaign must exist and have `status == completed`, or the request is rejected
    (HTTP 422). This is re-validated at resolution time too (both preview and send), so a campaign
    deleted or reverted after the segment was saved fails the resolve explicitly instead of
    silently widening the audience (a referenced-but-gone campaign would otherwise match zero
    `CampaignRecipient` rows, making every contact satisfy `has_not`).
  - **`CampaignActivityOp.HAS_NOT` semantics**: defined as "was sent this campaign and did not
    open/click it" — requires an *existing* `CampaignRecipient` row for the given `campaign_id`
    with the relevant timestamp column null. A contact who was never sent that campaign at all (no
    matching row) does **not** satisfy `has_not`:
    ```sql
    -- has_not(campaign_id, event) resolves to:
    EXISTS (
      SELECT 1 FROM campaign_recipient
      WHERE contact_id = contact.id
        AND campaign_id = :campaign_id
        AND {event}_at IS NULL
    )
    ```

  **Example rule trees** (shown as the `Segment.rule` JSON a validated `SegmentRuleCreate` would
  serialize to — enum members serialize to their string `.value`, e.g. `ListMembershipOp.IN` →
  `"in"`):

  - The PRD's original motivating case — "the other 15 of 20 who didn't open last month's
    campaign" — is a single leaf, no group needed:
    ```json
    {
      "root": {
        "type": "campaign_activity",
        "campaign_id": "3fa2...c9d1",
        "event": "opened",
        "op": "has_not"
      }
    }
    ```
  - "Everyone in the Newsletter list" — the trivial one-condition segment the campaign-builder's
    "pick a list" shortcut (Phase 2) creates behind the scenes:
    ```json
    {
      "root": {
        "type": "list_membership",
        "list_id": "9c11...44ab",
        "op": "in"
      }
    }
    ```
  - "In the Newsletter list AND clicked the Spring Sale campaign" — a two-leaf AND group, user
    story 4's reward/upsell case:
    ```json
    {
      "root": {
        "op": "and",
        "conditions": [
          {"type": "list_membership", "list_id": "9c11...44ab", "op": "in"},
          {"type": "campaign_activity", "campaign_id": "7ab0...12ef", "event": "clicked", "op": "has"}
        ]
      }
    }
    ```
  - "In list A OR in list B, but not the Newsletter list" — nested groups (an OR group nested
    inside an AND group; depth 2 of the allowed 5), exercising both group types together:
    ```json
    {
      "root": {
        "op": "and",
        "conditions": [
          {
            "op": "or",
            "conditions": [
              {"type": "list_membership", "list_id": "list-a-id", "op": "in"},
              {"type": "list_membership", "list_id": "list-b-id", "op": "in"}
            ]
          },
          {"type": "list_membership", "list_id": "newsletter-id", "op": "not_in"}
        ]
      }
    }
    ```
  - Phase 3b addition — "Company X AND did not open Campaign A" (user story 6's example),
    combining a `contact_field` leaf with a `campaign_activity` leaf:
    ```json
    {
      "root": {
        "op": "and",
        "conditions": [
          {"type": "contact_field", "field": "company", "operator": "==", "value": "Acme Inc"},
          {"type": "campaign_activity", "campaign_id": "3fa2...c9d1", "event": "opened", "op": "has_not"}
        ]
      }
    }
    ```
- **Segment repository/resolver**: a new deep module responsible for compiling a rule tree into a
  SQLAlchemy filter/query against `Contact`/`ContactListMember`/`CampaignRecipient`, and returning
  the resolved contact set for a given segment. This is the piece most worth isolating and testing
  in isolation — the rule tree's shape is the interface; callers never need to know how it's
  compiled to SQL. The resolver exposes both a "resolve contacts" query and a cheap "resolve count"
  variant (same compiled filter, wrapped in `COUNT(*)` instead of selecting rows) — the count is
  never persisted; it's recomputed on demand.
- **CRUD**: standard create/read/update/soft-delete for segments, following the existing repository
  pattern (`SoftDeleteRepository`, as used by `CampaignRepository`). New top-level router endpoints
  under `/segments` (not nested under `/contact-lists/{id}/...`, since a segment isn't owned by any
  one list).
- **Preview endpoint** (non-persisted stats): `GET /segments/{id}/preview` returns
  `{"contact_count": int}` for a saved segment, computed live via the resolver's count query — no
  caching, no new columns. `POST /segments/preview` accepts a raw rule tree body (same shape as
  `Segment.rule`) and returns the same shape, so the UI can show a live count while a segment is
  still being built/edited, before it's saved. Both routes reuse the same resolver code path as
  segment-to-contact-set resolution at send time, so the preview count and the actual send audience
  can never drift apart from independently-maintained logic.
- **Schema change**: replace `Campaign.contact_list_id` (currently required) with
  `Campaign.segment_id: UUID` (FK to `segments.id`, **required**). A campaign's audience is always
  "resolve this segment" — there's no longer a separate list step. This ships as a clean breaking
  schema change: no existing campaigns need to be migrated/backfilled, since there is no production
  data to preserve — existing campaign rows are dropped, not carried forward.
- **Send-flow change**: in `SendCampaignCommand` / the eligibility-filtering repository method
  (formerly `ContactListRepository.get_eligible_campaign_recipients`, now driven by segment rather
  than list), the segment's resolved contact set (this phase's resolver) is intersected with
  today's existing eligibility filter (active, has email, deduplicated by email) — the segment
  defines the target audience; the eligibility filter still applies on top of it, unchanged in its
  own logic.
- Phase 3 only adds `contact_field` conditions on top of this; it does not need its own schema
  cutover or send-flow change — both ship here, in Phase 2.
- **Segment-picker UX note** (backend-relevant only insofar as it shapes the API): for the common
  "just send to this whole list" case, the campaign-creation flow can offer a "pick a list"
  shortcut that transparently creates (or reuses) a trivial one-condition segment
  (`list_membership` only) behind the scenes, so the more general model doesn't add friction to the
  simple case. Exact UI is out of scope for this backend-only PRD, but the API must support
  creating a segment and referencing it from a campaign in the same flow without extra round trips
  becoming a UX problem. (Relocated here from an earlier draft's Phase 3, where it had been left
  behind after the `segment_id` cutover itself moved to this phase — see "Known Risks.")

### Phase 3a — `ContactType` enum + listing endpoint

Prerequisite for Phase 3b: `contact_type` is currently a free-text `String` column
(`app/models/contact.py`) with no allow-list anywhere, including on contact create/update
(`app/schemas/contact.py`). The contact-creation UI already offers a fixed dropdown (Personal,
Business, Vendor, Customer, Partner, Supplier, Lead), so this phase codifies that existing set as a
real enum rather than inventing a new one — closing a pre-existing validation gap, not just
supporting Phase 3b's segment condition.

- **New enum** `ContactType` (e.g. `app/schemas/contact.py` or a shared constants module), values
  matching the UI's existing set (lowercase, matching current data): `PERSONAL = "personal"`,
  `BUSINESS = "business"`, `VENDOR = "vendor"`, `CUSTOMER = "customer"`, `PARTNER = "partner"`,
  `SUPPLIER = "supplier"`, `LEAD = "lead"`.
- **Schema change**: `contact_type: str` fields in `app/schemas/contact.py` (create, update, and
  read schemas) become `contact_type: ContactType`, so invalid values are rejected (422) on
  contact create/update, not just when building a segment. Existing test fixtures only use
  `"personal"`/`"business"`, so this cutover doesn't break current tests.
- **New endpoint** `GET /contacts/contact-types`, returning the fixed set as `{id, name}` pairs
  (e.g. `{"id": "personal", "name": "Personal"}`), wrapped in the same `Page[T]`
  (`fastapi_pagination`) structure used by other list endpoints (see `app/routers/contact.py`'s
  `GET /contacts`), even though the underlying data is a static in-memory list rather than a
  paginated DB query. Lets the segment-builder UI (and the contact-creation UI) drive the dropdown
  from the API instead of hardcoding the list client-side.

### Phase 3b — Contact-field conditions

Completes the general filter engine (user story 5), additive on top of Phase 2's already-usable
segment→campaign flow, depending on Phase 3a's `ContactType` enum for validating `contact_type`
condition values.

- **Rule tree extension**: add a third leaf condition type, `contact_field`, following the same
  named-constant rule as Phase 2's leaves (no bare string literals for field names or operators):

  ```python
  class ContactFieldName(str, Enum):
      CONTACT_TYPE = "contact_type"
      COMPANY = "company"
      CITY = "city"
      STATE = "state"
      COUNTRY = "country"
      IS_ACTIVE = "is_active"

  class ContactFieldOp(str, Enum):
      EQ = "=="
      NEQ = "!="
      ILIKE = "ilike"
      IN = "in"

  # Not every operator is meaningful for every field (e.g. `ilike`/`in` on the boolean
  # is_active column would fail at the SQL layer or produce a nonsense query). Validated in
  # ContactFieldCondition below, not left to apply_filters' permissive fallback.
  ALLOWED_OPS_BY_FIELD: dict[ContactFieldName, frozenset[ContactFieldOp]] = {
      ContactFieldName.CONTACT_TYPE: frozenset(ContactFieldOp),
      ContactFieldName.COMPANY: frozenset(ContactFieldOp),
      ContactFieldName.CITY: frozenset(ContactFieldOp),
      ContactFieldName.STATE: frozenset(ContactFieldOp),
      ContactFieldName.COUNTRY: frozenset(ContactFieldOp),
      ContactFieldName.IS_ACTIVE: frozenset({ContactFieldOp.EQ, ContactFieldOp.NEQ}),
  }

  class ContactFieldCondition(BaseModel):
      type: Literal[ConditionType.CONTACT_FIELD] = ConditionType.CONTACT_FIELD
      field: ContactFieldName
      operator: ContactFieldOp
      value: str | bool | list[str]

      @model_validator(mode="after")
      def enforce_field_op_and_value_type(self) -> "ContactFieldCondition":
          if self.operator not in ALLOWED_OPS_BY_FIELD[self.field]:
              raise ValueError(f"operator {self.operator} not allowed for field {self.field}")
          if self.field is ContactFieldName.IS_ACTIVE and not isinstance(self.value, bool):
              raise ValueError("is_active requires a boolean value")
          if self.operator is ContactFieldOp.IN and not isinstance(self.value, list):
              raise ValueError("in requires a list value")
          if self.field is ContactFieldName.CONTACT_TYPE:
              values = self.value if isinstance(self.value, list) else [self.value]
              if not all(v in set(ContactType) for v in values):
                  raise ValueError("contact_type value must be a known ContactType")
          return self
  ```

  `field` is restricted to `ContactFieldName`'s fixed allow-list of existing `Contact` columns;
  `operator` is restricted per-field by `ALLOWED_OPS_BY_FIELD` above, itself a subset of what
  `apply_filters` (`app/utils/db/filtering.py`) supports — this condition type should reuse
  `apply_filters`'s comparison logic once `operator` has already been validated, never pass a raw
  unvalidated string into it. `Leaf` becomes
  `Union[ListMembershipCondition, CampaignActivityCondition, ContactFieldCondition]`.
- No cross-segment/cross-list validation is needed at this point (unlike the earlier
  list-scoped design) — since a segment is never tied to a specific list, there's no "segment's
  list must match campaign's list" rule to enforce.

## Testing Decisions

Good tests here exercise external behavior — "given this rule tree and this database state, which
contacts come back" / "given this campaign and window, which recipients get their timestamps
updated" — not internal call sequencing. Prior art: `tests/app/repositories/test_campaign_repository.py`
and `tests/app/tasks/test_poll_campaign_status.py` already test at this level (repository methods
and the Celery task's DB effects, not mocked-out internals).

- **Phase 1**:
  - New task test (sibling to `tests/app/tasks/test_poll_campaign_status.py`) covering: a
    `completed` campaign inside its window gets its recipients'
    `opened_at`/`clicked_at` and the campaign's result counts updated from a stubbed Sendly
    response; a campaign outside its window is skipped; one campaign's lookup failure doesn't stop
    the others (matches the existing per-item try/except pattern).
  - `CampaignRepository`/model-level test that a completed campaign's counts round-trip correctly.
- **Phase 2**:
  - The segment resolver is the module most worth isolating and testing thoroughly in isolation —
    for a range of rule trees (single condition, AND, OR, nested groups, `has`/`has_not`,
    `in`/`not_in`) against seeded `Contact`/`ContactListMember`/`CampaignRecipient` fixtures,
    assert exactly which contacts resolve. Explicitly include a rule tree with zero
    `list_membership` conditions and confirm it resolves against the whole contact base.
  - Repository-level CRUD tests for `Segment`, following `tests/app/repositories/test_contact_list_repository.py`'s
    style (soft delete), minus any list-scoping assertions since none apply.
  - Router tests for the new top-level `/segments` endpoints, including both preview routes: the
    saved-segment `GET /segments/{id}/preview` and the draft `POST /segments/preview`, asserting
    the returned `contact_count` matches the resolver's count query against seeded fixtures.
  - A resolver test asserting the "resolve count" path and the "resolve contacts" path agree
    (`count == len(resolved_contacts)`) across the same range of rule trees used elsewhere in
    Phase 2's resolver tests, so the two code paths can't silently drift.
  - Lifecycle-validation tests: creating/updating a segment with a `campaign_activity.campaign_id`
    that doesn't exist or isn't `completed` is rejected (422); a segment that resolved fine at save
    time fails explicitly at resolution if the referenced campaign is later deleted/un-completed.
  - `has_not` semantics test: a contact never sent the referenced campaign does not satisfy
    `has_not`, distinguishing "sent and didn't open" from "never sent."
  - `SendCampaignCommand` test asserting a campaign sends only to the intersection of
    segment-resolved contacts and today's existing eligibility filter — extending
    `tests/app/commands/test_send_campaign_command.py`.
  - A test that a campaign's `segment_id` is required (schema/DB level) and that a segment with no
    `list_membership` condition resolves and sends correctly across contacts from multiple lists.
- **Phase 3a**:
  - Schema tests: contact create/update rejects a `contact_type` value outside `ContactType`
    (422); accepts each of the seven enum values.
  - Router test for `GET /contacts/contact-types`: returns all seven `{id, name}` pairs in the
    standard `Page[T]` shape.
- **Phase 3b**:
  - Resolver tests extended to cover `contact_field` conditions and mixed AND/OR trees combining
    all three condition types.
  - Validation tests: an operator not in `ALLOWED_OPS_BY_FIELD` for the given field (e.g. `ilike`
    on `is_active`) is rejected (422); a `contact_type` value outside `ContactType` is rejected
    (422); an `in` operator with a non-list value is rejected (422).

Ask the user which of these modules they want tests written for before implementation begins on
each phase — this PRD identifies the segment resolver (Phase 2) as the highest-value module to get
right, since every later phase and the send flow itself depends on its correctness.

## Out of Scope

- A custom-fields/tags system on `Contact` — condition types are restricted to existing columns.
  Adding tags is a separate project.
- Persisting the segment's contact count (e.g. a `contact_count` column updated on some schedule).
  The count in Phase 2's preview endpoint is deliberately always computed live — persisting it
  would require cache-invalidation logic every time underlying `Contact`/`ContactListMember`/
  `CampaignRecipient` data changes, which is unnecessary complexity for a number whose only job is
  to warn the user in the moment they're looking at it.
- Anything beyond `contact_count` in the preview response (estimated deliverability, engagement
  rate forecasts, etc.) — Phase 2 ships the count only.
- Requiring every segment to include at least one `list_membership` condition — considered and
  explicitly rejected; segments may resolve against the entire contact base with no list filter at
  all. See "Solution" and Phase 2's rule tree notes.
- "Did not open **any** campaign" (as opposed to a specific named campaign) as a condition variant —
  not included in Phase 2's `campaign_activity` condition; would need its own design if wanted.
- Per-campaign override of the polling window — Phase 1 ships a single global default only.
- Any API/UI design beyond the endpoint shapes noted per phase — no frontend work is scoped here;
  this PRD is backend/data-model only.
- Full mirroring of Sendly's delivery-event history (bounces, complaints, multiple opens/clicks per
  recipient with timestamps) — the cache is deliberately restricted to first-occurrence
  `opened_at`/`clicked_at`.
- Migrating/backfilling existing `Campaign.contact_list_id` data — there is no production data to
  preserve; Phase 2 ships `segment_id` as a required column with existing campaign rows dropped,
  not converted.

## Known Risks (from design review)

This PRD was reviewed before implementation began. The findings below are folded in here
(the standalone review doc has been removed) so risks stay attached to the design they apply to,
rather than living in a separate file that can drift out of sync. Findings are ordered by
severity; each has been revalidated against the current design and the current state of `sendly`
and `tessera-sdk-py` (both under `~/sites/linden-family/`) as of 2026-08-29.

- **[RESOLVED] Sendly click data.** Originally: Sendly's `Email` model/schema and broadcast
  response exposed only `opened_at`, not `clicked_at`/`clicked_count`, which Phase 1 depends on.
  As of 2026-08-29, `sendly/app/models/email.py` has both `opened_at` and `clicked_at` columns,
  `sendly/app/schemas/email.py` and `sendly/app/schemas/broadcast.py` expose `clicked_at` and
  `clicked_count` respectively, and the SDK's `GetBroadcastResponse` is in sync. No further action
  needed — Phase 1 can be implemented as written.

- **[RESOLVED] Pagination on `list_emails()`/`list_broadcast_recipients()`.** Sendly's paginated
  endpoints (`sendly/app/routers/email.py`, `.../broadcasts/{batch_id}/recipients`) return proper
  `total`/`page`/`size`/`pages` metadata, but the SDK's plain `list_emails()` and
  `list_broadcast_recipients()` each still return a single page. Merged into `tessera-sdk-py`:
  `iter_emails(...)` and `iter_broadcast_recipients(...)`, generators that transparently loop
  `page` until `page >= pages` and yield every matching row across all pages. Phase 1's polling
  task should use `iter_broadcast_recipients(batch_id=batch_id)` specifically (not `iter_emails`)
  — its `BroadcastRecipientResult` carries `client_reference_id` back, which is what resolves the
  mutable-email risk below.

- **[OPEN, cheaper fix now available] Engagement can't reliably map back to a mutable contact.**
  `CampaignRecipient` stores only `campaign_id` and `contact_id`; the polling task is expected to
  match Sendly results by recipient email. If a contact's email changes after a campaign was sent,
  polling returns the old address, matches nothing, and that recipient is permanently
  misclassified as a non-opener.
  Originally recommended: add an immutable `sent_email` column to `CampaignRecipient`. A cheaper
  fix is now available instead — `tessera-sdk-py`'s `BroadcastRecipient` schema already has a
  `client_reference_id: Optional[UUID]` field created exactly for this ("correlating this
  recipient with its results later ... without matching on the mutable email address"), and
  `iter_broadcast_recipients()` (added in the pagination fix above) returns it back on each
  `BroadcastRecipientResult`. Confirmed as of 2026-08-29:
  `app/commands/campaign/send_campaign_command.py`'s `_to_broadcast_recipient` (lines 134–146)
  does **not** currently set `client_reference_id` when building the `BroadcastRecipient` sent to
  Sendly, even though `mark_sending` (lines 120–124) already has `recipient_contact_ids` in hand
  at send time. **Action required** (Phase 1): set `client_reference_id=contact.id` (or
  `campaign_recipient.id`, if that row is created before send) in `_to_broadcast_recipient`, then
  have the polling task match `iter_broadcast_recipients()` rows back to `CampaignRecipient` by
  `client_reference_id` instead of by email — no new column needed, and the match survives a
  contact's email changing after send.

- **[SCHEMA DEFINED, not yet implemented] Unconstrained recursive rule trees are a
  resource-exhaustion surface.** Originally: the rule tree was specified only loosely as recursive
  JSON with `Any` leaf values and open-ended operators — the reused `apply_filters` utility
  (`app/utils/db/filtering.py`) silently ignores invalid fields and coerces unknown operators into
  equality rather than rejecting them, so a caller could submit thousands of nested OR groups or
  huge `in` lists, producing expensive SQL or recursion failures. Phase 2's "Rule tree schema"
  above now pins this down precisely: discriminated Pydantic models (`RuleGroup`/`Leaf` union,
  `Field(discriminator="type")`), `MAX_TREE_DEPTH = 5`, `MAX_LEAVES = 25`, `MAX_STRING_LENGTH =
  255`, `MAX_IN_VALUES = 100`, and a depth/leaf-count validator that rejects anything over those
  limits — no raw JSON accepted, no reliance on `apply_filters`'s permissive fallback. **Remaining
  action**: implement this schema in Phase 2's actual code (`app/schemas/segment.py` or similar);
  the design above is not yet code. Phase 3's `contact_field` condition must be added to the same
  `Leaf` union with its own bounded field/operator/value-type allow-list, not left to
  `apply_filters`'s defaults.

- **[RESOLVED] `campaign_activity` references lack lifecycle validation.** Nothing required a
  `campaign_activity.campaign_id` to reference a campaign that actually exists or has completed —
  a segment referencing a draft, deleted, or never-existent campaign would resolve every contact as
  `has_not` opened/clicked it (no matching `CampaignRecipient` rows exist), silently producing a
  much broader audience than intended. Resolved by decision: on segment create/update, every
  referenced `campaign_activity.campaign_id` must exist and be `completed` (422 otherwise); the
  same check is re-run at resolution time (preview and send), so a campaign deleted after the
  segment was saved fails explicitly rather than silently widening the audience. See Phase 2's rule
  tree section for the implementation.

- **[RESOLVED] `has_not` had no defined set semantics.** It was unspecified whether a contact who
  was never sent the referenced campaign at all (no `CampaignRecipient` row) counts as "has not
  opened" it. Resolved by decision: `has_not` requires an *existing* `CampaignRecipient` row for
  the referenced campaign with the relevant timestamp column null — i.e., "was sent it and didn't
  open/click it," not "wasn't sent it." Contacts never sent that campaign do not qualify as
  `has_not`. See Phase 2's rule tree section for the SQL definition.

- **[RESOLVED] The "data as of" indicator had no trustworthy timestamp to point at.** The schema
  added engagement values but no successful-sync timestamp, and polling deliberately swallows
  per-item failures (matching the existing `poll_campaign_status` pattern) — if refreshes failed
  silently for days, the UI had nothing but `completed_at` or the polling-window end to infer
  freshness from, and would present stale data as current. Resolved by decision: Phase 1 adds
  `engagement_last_synced_at` (updated only after a fully successful refresh pass — left untouched
  on a partial failure) and a fixed `engagement_polling_expires_at` to `Campaign`, both exposed
  through the API so the results UI can build an honest "data as of" indicator.

- **[RESOLVED] Claimed phase value contradicted the phase boundaries.** Further Notes below claimed
  "Phase 2 alone already solves the original 'exclude prior openers' problem," but Phase 2 as
  originally scoped excluded attaching/applying a segment to a campaign — that was Phase 3. As
  written, after Phases 1 and 2 shipped, a user still could not actually send a follow-up campaign
  restricted to a segment. Resolved by decision: `Campaign.segment_id`, its breaking schema
  cutover, and send-time segment resolution moved into Phase 2 — `list_membership`/
  `campaign_activity` segments are now usable end-to-end (build → attach to campaign → send) before
  `contact_field` conditions exist. Phase 3 is now purely additive (`contact_field`, split into
  Phase 3a's `ContactType` enum/endpoint prerequisite and Phase 3b's leaf condition). See Phase 2
  and Phase 3a/3b above for the updated scope.

## Further Notes

- The `tessera-sdk` changes Phase 1 depends on (`GetBroadcastResponse` count fields, a
  per-email/batch listing method) were handled outside this PRD, in `tessera-sdk-py`, and have
  already been merged and released. Phase 1 work is unblocked.
- This PRD represents a deliberate, scoped reversal of a rule currently stated in
  `docs/campaign.md` ("Looply must not create its own... delivery-event table... Sendly is the
  source of truth for those concerns"). Phase 1 must update that document to describe the new
  `opened_at`/`clicked_at` cache and its bounded-window/staleness trade-off honestly, rather than
  leaving the doc contradicting the code.
- **Design history**: an earlier version of this PRD scoped every `Segment` to exactly one
  `contact_list_id`, mirroring Mailchimp's Audience-scoped segments. That was reconsidered because
  it forced a rigid two-step flow (list, then segment-on-list) and made segments non-reusable
  across lists, even though `ContactListMember` already supports many-to-many list membership. The
  current design (Loops.so-style: list membership as just one filter condition, segments fully
  list-agnostic) removes that rigidity at the cost of allowing a segment to resolve to the entire
  contact base if the user builds it that way — an accepted trade-off, mitigated by Phase 2's
  non-persisted `contact_count` preview endpoint, which lets the UI warn the user in the moment
  rather than after a campaign is already sent.
- The phase boundaries are chosen so each is independently valuable: Phase 1 alone already answers
  "did my campaign work" inside Looply; Phase 2 alone already solves the original "exclude prior
  openers" problem end-to-end — segment build, campaign attachment, and send all ship together in
  this phase (and it subsumes "target a specific list," via `list_membership`) — even before
  contact-field conditions exist; Phase 3a closes a pre-existing gap (unvalidated `contact_type`)
  by codifying the UI's existing fixed set as a `ContactType` enum and a listing endpoint; Phase 3b
  completes the general filter engine with the `contact_field` condition, additive on top of Phase
  2's already-usable segment→campaign flow and depending on Phase 3a's enum. Phases can be
  re-sequenced or split further if needed, but this ordering ships the original problem's full
  solution (Phase 2) as early as possible.

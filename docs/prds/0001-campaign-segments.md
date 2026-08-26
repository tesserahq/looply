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

Introduce **Segments**: a saved, reusable, rule-based filter scoped to one contact list, the same
way Mailchimp scopes a Segment to one Audience. A segment narrows down a base contact list using
conditions — initially, past campaign engagement (opened/clicked a specific prior campaign) and
existing contact fields (company, contact type, city, state, country, active status) — combined
with AND/OR logic. A campaign keeps its required base contact list and gains an optional segment
that narrows it at send time.

This requires Looply to start caching a thin slice of engagement data it deliberately doesn't
store today: `opened_at`/`clicked_at` per recipient, and campaign-level result counts, refreshed by
polling Sendly for a bounded window after a campaign completes. This is a conscious, scoped
reversal of the rule in `docs/campaign.md` that Looply must not duplicate Sendly's delivery-event
data — that document must be updated alongside this work, not left contradicting the code.

The work is split into phases so each lands as an independently shippable, coherent slice rather
than one large change. Phase 1 depends on `tessera-sdk` changes being handled separately — see
"Implementation Decisions."

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
6. As a campaign sender, I want to combine multiple conditions with AND/OR logic, so that I can
   express rules like "in Company X AND did not open Campaign A."
7. As a campaign sender, I want to save a segment with a name and reuse it across multiple
   campaigns, so that I don't have to rebuild the same filter every time I send a related
   follow-up.
8. As a campaign sender, I want a segment to always be scoped to one contact list, so that I never
   accidentally attach a segment built for one audience to a campaign targeting a different one.
9. As a campaign sender, I want a draft campaign to optionally reference a saved segment on top of
   its required contact list, so that existing campaigns (which have no segment) keep working
   exactly as they do today.
10. As a campaign sender, I want the segment's conditions to be evaluated at send time (same moment
    today's active/has-email eligibility check runs), so that the audience reflects the latest
    cached engagement data available when I actually send.
11. As a campaign sender, I want to understand that engagement caching has a bounded window (not
    indefinite), so that I'm not surprised if someone who opens after that window still receives a
    follow-up campaign meant to exclude them.
12. As a developer maintaining Looply, I want the engagement cache to be a narrow, clearly-scoped
    addition (timestamps only, not a full event log), so that Looply's stated boundary with Sendly
    stays intentional and legible rather than silently eroding.
13. As a developer maintaining Looply, I want the segment rule tree to be evaluated by compiling it
    into SQLAlchemy filters against local tables, so that resolving a segment's audience is a single
    local query, not a live call out to Sendly on every campaign build or send.

## Implementation Decisions

### Phase 1 — Engagement cache + campaign result counts (no segments yet)

Depends on `tessera-sdk`'s `SendlyClient` exposing the count fields (`delivered_count`,
`bounced_count`, `complained_count`, `opened_count`) on `GetBroadcastResponse` and a per-email
method (e.g. `list_emails(batch_id)`, wrapping Sendly's `GET /emails?batch_id=...`) returning each
recipient's email plus `opened_at`/`clicked_at`. That SDK work is being handled separately and
isn't part of this PRD; this phase assumes it lands first.

Ships a visible, standalone improvement (user story 1–2) and builds the data foundation everything
else depends on.

- **Schema**: add `opened_at: datetime | None` and `clicked_at: datetime | None` to
  `CampaignRecipient` (`app/models/campaign_recipient.py`). Deliberately narrow — timestamps only,
  first-occurrence semantics, not a per-event log. This is the one piece of "delivery event" data
  Looply will now own; `docs/campaign.md` gets updated in this phase to describe it honestly as a
  scoped exception rather than leaving the "must not duplicate" line contradicted by the code.
- **Schema**: add result-count columns to `Campaign` (`delivered_count`, `bounced_count`,
  `complained_count`, `opened_count`, `clicked_count`) — currently nothing is stored; today's
  `poll_campaign_status` task only reads `finished` to flip status, then discards the rest of the
  response.
- **New background task**, following the existing `poll_campaign_status` pattern
  (`app/tasks/poll_campaign_status.py`, same `build_sendly_client()` + per-item try/except so one
  bad lookup doesn't stop the batch): for each `completed` campaign still inside its polling
  window, call the new SDK `list_emails(batch_id)` and update matching `CampaignRecipient` rows'
  `opened_at`/`clicked_at`, and call `get_broadcast()` to refresh the campaign's result counts.
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

### Phase 2 — `Segment` model + campaign-activity conditions

Ships the ability to build and save a segment based on prior-campaign engagement (user stories
3–4, 7–8), the narrowest version of the feature that solves the original problem.

- **New model** `Segment` (new file, e.g. `app/models/segment.py`), following existing model
  conventions (`TimestampMixin`, `SoftDeleteMixin`, UUID PK, `created_by_id` FK to `users`):
  - `name: str`
  - `contact_list_id: UUID` (FK to `contact_lists.id`, required — a segment is always scoped to
    exactly one list, matching Mailchimp's Audience-scoped segments; this also means condition
    types never need to express list membership themselves)
  - `rule: JSONB` — the condition tree (see "Rule tree" below)
  - `created_by_id: UUID` (FK to `users.id`)
- **Rule tree schema** (defined precisely in this phase, not before): a nested structure of groups
  (`{"op": "and" | "or", "conditions": [...]}`) and leaf conditions. Phase 2 supports exactly one
  leaf condition type: `campaign_activity` — `{"type": "campaign_activity", "campaign_id": UUID,
  "event": "opened" | "clicked", "op": "has" | "has_not"}`. Resolved as a join against
  `CampaignRecipient` filtered to the given `campaign_id`, checking whether the relevant timestamp
  column is set.
- **Segment repository/resolver**: a new deep module responsible for compiling a rule tree into a
  SQLAlchemy filter/query against `Contact`/`ContactListMember`/`CampaignRecipient`, and returning
  the resolved contact set for a given segment. This is the piece most worth isolating and testing
  in isolation — the rule tree's shape is the interface; callers never need to know how it's
  compiled to SQL.
- **CRUD**: standard create/read/update/soft-delete for segments, scoped to their `contact_list_id`,
  following the existing repository pattern (`SoftDeleteRepository`, as used by
  `CampaignRepository`). New router endpoints under something like `/contact-lists/{id}/segments`,
  mirroring the nesting style already used for `/contact-lists/{id}/members`.
- Campaign wiring (attaching a segment to a campaign, and using it at send time) is explicitly
  **not** part of Phase 2 — this phase only makes segments buildable, saveable, and resolvable to a
  contact set on their own.

### Phase 3 — Contact-field conditions + campaign send-time wiring

Completes the feature end-to-end (user stories 5, 6, 9–10).

- **Rule tree extension**: add a second leaf condition type, `contact_field` —
  `{"type": "contact_field", "field": str, "operator": str, "value": Any}`, restricted to a fixed
  allow-list of existing `Contact` columns (`contact_type`, `company`, `city`, `state`, `country`,
  `is_active`) and the operators already supported by the existing `apply_filters` utility
  (`app/utils/db/filtering.py`) — `==`, `!=`, `ilike`, `in`, etc. This condition type should reuse
  `apply_filters`'s operator table rather than reimplementing comparison logic.
- **Schema change**: add `segment_id: UUID | None` to `Campaign` (FK to `segments.id`, nullable).
  `contact_list_id` remains required and unchanged — no migration needed for existing campaigns,
  since a campaign with no `segment_id` behaves exactly as today.
- **Send-flow change**: in `SendCampaignCommand` / `ContactListRepository.get_eligible_campaign_recipients`,
  when a campaign has a `segment_id`, the segment's resolved contact set (Phase 2's resolver,
  scoped to the campaign's own `contact_list_id`) is intersected with today's existing eligibility
  filter (active, has email, deduplicated by email) — the segment narrows, it never replaces,
  today's eligibility rules.
- **Validation**: creating/updating a campaign with a `segment_id` must reject a segment whose
  `contact_list_id` doesn't match the campaign's `contact_list_id` — enforced at the point Segment
  scoping is meaningful at all.

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
    for a range of rule trees (single condition, AND, OR, nested groups, `has`/`has_not`) against
    seeded `Contact`/`CampaignRecipient` fixtures, assert exactly which contacts resolve.
  - Repository-level CRUD tests for `Segment`, following `tests/app/repositories/test_contact_list_repository.py`'s
    style (soft delete, scoping to `contact_list_id`).
  - Router tests for the new segment endpoints, following `tests/app/routers/test_contact_list.py`.
- **Phase 3**:
  - Resolver tests extended to cover `contact_field` conditions and mixed AND/OR trees combining
    both condition types.
  - `SendCampaignCommand` test asserting a campaign with a `segment_id` sends only to the
    intersection of segment-resolved contacts and today's existing eligibility filter — extending
    `tests/app/commands/test_send_campaign_command.py`.
  - A validation test that attaching a segment scoped to a different `contact_list_id` than the
    campaign's is rejected.

Ask the user which of these modules they want tests written for before implementation begins on
each phase — this PRD identifies the segment resolver (Phase 2) as the highest-value module to get
right, since every later phase and the send flow itself depends on its correctness.

## Out of Scope

- A custom-fields/tags system on `Contact` — condition types are restricted to existing columns.
  Adding tags is a separate project.
- Segments spanning multiple contact lists, or list-agnostic/reusable-anywhere segments — segments
  are always scoped to exactly one list, matching Mailchimp.
- A live "estimated recipient count" preview while building a segment (Mailchimp has this) — not
  committed to any phase here; worth a follow-up PRD once segments exist and usage patterns are
  clearer.
- "Did not open **any** campaign" (as opposed to a specific named campaign) as a condition variant —
  not included in Phase 2's `campaign_activity` condition; would need its own design if wanted.
- Per-campaign override of the polling window — Phase 1 ships a single global default only.
- Any API/UI design beyond the endpoint shapes noted per phase — no frontend work is scoped here;
  this PRD is backend/data-model only.
- Full mirroring of Sendly's delivery-event history (bounces, complaints, multiple opens/clicks per
  recipient with timestamps) — the cache is deliberately restricted to first-occurrence
  `opened_at`/`clicked_at`.

## Further Notes

- The `tessera-sdk` changes Phase 1 depends on (`GetBroadcastResponse` count fields, a
  per-email/batch listing method) are being handled outside this PRD, in `tessera-sdk-py`. Phase 1
  work should not start until that lands.
- This PRD represents a deliberate, scoped reversal of a rule currently stated in
  `docs/campaign.md` ("Looply must not create its own... delivery-event table... Sendly is the
  source of truth for those concerns"). Phase 1 must update that document to describe the new
  `opened_at`/`clicked_at` cache and its bounded-window/staleness trade-off honestly, rather than
  leaving the doc contradicting the code.
- The phase boundaries are chosen so each is independently valuable: Phase 1 alone already answers
  "did my campaign work" inside Looply; Phase 2 alone already solves the original "exclude prior
  openers" problem for the campaign-activity case even before contact-field conditions exist;
  Phase 3 completes the general filter engine. Phases can be re-sequenced or split further if
  needed, but this ordering was chosen to ship the original problem's solution (Phase 2) as early
  as possible.

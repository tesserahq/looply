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
- **New background task**, following the existing `poll_campaign_status` pattern
  (`app/tasks/poll_campaign_status.py`, same `build_sendly_client()` + per-item try/except so one
  bad lookup doesn't stop the batch): for each `completed` campaign still inside its polling
  window, call the SDK's `iter_emails(batch_id=batch_id)` (not `list_emails()` — the plain method
  returns only a single page; `iter_emails()` transparently walks every page so campaigns with
  more than 50 recipients aren't silently truncated) and update matching `CampaignRecipient` rows'
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

### Phase 2 — `Segment` model, rule engine (list membership + campaign-activity conditions)

Ships the ability to build and save a list-agnostic segment based on list membership and
prior-campaign engagement (user stories 3–4, 6–8), the narrowest version of the feature that
solves the original problem without hard-coding a list scope.

- **New model** `Segment` (new file, e.g. `app/models/segment.py`), following existing model
  conventions (`TimestampMixin`, `SoftDeleteMixin`, UUID PK, `created_by_id` FK to `users`):
  - `name: str` (unique per account/workspace, not per-list — segments are no longer namespaced
    under a list)
  - `rule: JSONB` — the condition tree (see "Rule tree" below)
  - `created_by_id: UUID` (FK to `users.id`)
  - Deliberately **no** `contact_list_id` column. A segment has no owning list; any relationship to
    a list exists only inside its rule tree, as a `list_membership` condition.
- **Rule tree schema** (defined precisely in this phase, not before): a nested structure of groups
  (`{"op": "and" | "or", "conditions": [...]}`) and leaf conditions. Phase 2 supports two leaf
  condition types:
  - `list_membership` — `{"type": "list_membership", "list_id": UUID, "op": "in" | "not_in"}`.
    Resolved as a join against `ContactListMember` filtered to the given `list_id`, checking
    `deleted_at IS NULL` for `in` (or its absence for `not_in`). This is what makes "everyone in
    list X" expressible without a segment needing a dedicated list-scope column.
  - `campaign_activity` — `{"type": "campaign_activity", "campaign_id": UUID, "event": "opened" |
    "clicked", "op": "has" | "has_not"}`. Resolved as a join against `CampaignRecipient` filtered
    to the given `campaign_id`, checking whether the relevant timestamp column is set.
  - A rule tree with **zero** `list_membership` conditions is valid and resolves against the
    account's entire contact base — see "Out of Scope" for why this is intentionally unguarded.
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
- Campaign wiring (attaching a segment to a campaign, and using it at send time) is explicitly
  **not** part of Phase 2 — this phase only makes segments buildable, saveable, and resolvable to a
  contact set on their own.

### Phase 3 — Contact-field conditions + campaign send-time wiring

Completes the feature end-to-end (user stories 5, 9–11).

- **Rule tree extension**: add a third leaf condition type, `contact_field` —
  `{"type": "contact_field", "field": str, "operator": str, "value": Any}`, restricted to a fixed
  allow-list of existing `Contact` columns (`contact_type`, `company`, `city`, `state`, `country`,
  `is_active`) and the operators already supported by the existing `apply_filters` utility
  (`app/utils/db/filtering.py`) — `==`, `!=`, `ilike`, `in`, etc. This condition type should reuse
  `apply_filters`'s operator table rather than reimplementing comparison logic.
- **Schema change**: replace `Campaign.contact_list_id` (currently required) with
  `Campaign.segment_id: UUID` (FK to `segments.id`, **required**). A campaign's audience is always
  "resolve this segment" — there's no longer a separate list step. No existing campaigns need to be
  migrated/backfilled; this ships as a clean breaking schema change (existing campaign rows are
  dropped, not carried forward).
- **Send-flow change**: in `SendCampaignCommand` / the eligibility-filtering repository method
  (formerly `ContactListRepository.get_eligible_campaign_recipients`, now driven by segment rather
  than list), the segment's resolved contact set (Phase 2's resolver) is intersected with today's
  existing eligibility filter (active, has email, deduplicated by email) — the segment defines the
  target audience; the eligibility filter still applies on top of it, unchanged in its own logic.
- **Segment-picker UX note** (backend-relevant only insofar as it shapes the API): for the common
  "just send to this whole list" case, the campaign-creation flow can offer a "pick a list"
  shortcut that transparently creates (or reuses) a trivial one-condition segment
  (`list_membership` only) behind the scenes, so the more general model doesn't add friction to the
  simple case. Exact UI is out of scope for this backend-only PRD, but the API must support
  creating a segment and referencing it from a campaign in the same flow without extra round trips
  becoming a UX problem.
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
- **Phase 3**:
  - Resolver tests extended to cover `contact_field` conditions and mixed AND/OR trees combining
    all three condition types.
  - `SendCampaignCommand` test asserting a campaign sends only to the intersection of
    segment-resolved contacts and today's existing eligibility filter — extending
    `tests/app/commands/test_send_campaign_command.py`.
  - A test that a campaign's `segment_id` is required (schema/DB level) and that a segment with no
    `list_membership` condition resolves and sends correctly across contacts from multiple lists.

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
  preserve; Phase 3 ships `segment_id` as a required column with existing campaign rows dropped,
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

- **[RESOLVED] Pagination on `list_emails()`.** Sendly's `GET /emails` endpoint
  (`sendly/app/routers/email.py`) implements proper server-side pagination via
  `fastapi-pagination`, returning `total`/`page`/`size`/`pages` metadata. The SDK's
  `SendlyClient.list_emails()` still returns a single page, but
  `tessera-sdk-py/tessera_sdk/clients/sendly/client.py` now also exposes
  `iter_emails(project_id=..., batch_id=..., tag=..., status=..., size=...)`, a generator that
  transparently loops `page` until `page >= pages` and yields every matching email across all
  pages. Phase 1's background task should call `iter_emails(batch_id=batch_id)` rather than
  `list_emails()` directly, so a broadcast with more than one page of recipients (>50 by default)
  is fully consumed rather than silently truncated. The same fix was applied to
  `list_broadcast_recipients()` via a parallel `iter_broadcast_recipients()` generator, since it
  had the identical single-page limitation — worth using instead of `iter_emails()` if Phase 1
  ends up preferring `list_broadcast_recipients`'s typed, `client_reference_id`-aware response
  (see the mutable-email finding below).

- **[OPEN] Engagement can't reliably map back to a mutable contact.** `CampaignRecipient` stores
  only `campaign_id` and `contact_id`; the polling task is expected to match Sendly results by
  recipient email. If a contact's email changes after a campaign was sent, polling returns the
  old address, matches nothing, and that recipient is permanently misclassified as a non-opener.
  **Action required**: add an immutable `sent_email` column to `CampaignRecipient`, populated in
  the same transaction as the send snapshot, and match Sendly rows against
  `(campaign_id, sent_email)` rather than the contact's current (mutable) email. Add to Phase 1.

- **[OPEN] Unconstrained recursive rule trees are a resource-exhaustion surface.** The rule tree
  is currently specified as free-form recursive JSON with `Any` leaf values and open-ended
  operators. The reused `apply_filters` utility (`app/utils/db/filtering.py`) silently ignores
  invalid fields and coerces unknown operators into equality rather than rejecting them. A caller
  could submit thousands of nested OR groups or huge `in` lists, producing expensive SQL or
  recursion failures; invalid operators could also execute with surprising semantics.
  **Action required** (Phase 2): define discriminated Pydantic schemas for the rule tree instead
  of accepting raw JSON, and enforce explicit limits — e.g. max depth 5, max 25 leaves, bounded
  string/list value sizes. Define an explicit field × operator × value-type matrix per condition
  type and reject anything outside it with HTTP 422, rather than exposing `apply_filters`'s
  permissive fallback behavior directly to segment input.

- **[OPEN] `campaign_activity` references lack lifecycle validation.** Nothing requires a
  `campaign_activity.campaign_id` to reference a campaign that actually exists or has completed.
  A segment referencing a draft, deleted, or never-existent campaign resolves every contact as
  `has_not` opened/clicked it (no matching `CampaignRecipient` rows exist), silently producing a
  much broader audience than intended instead of failing explicitly. **Action required** (Phase 2):
  on segment create/update, require every referenced `campaign_activity.campaign_id` to exist and
  be `completed`; revalidate this at resolution time too, so a campaign deleted after the segment
  was saved fails explicitly rather than silently widening the audience.

- **[OPEN] `has_not` has no defined set semantics.** It's unspecified whether a contact who was
  never sent the referenced campaign at all (no `CampaignRecipient` row) counts as "has not
  opened" it. An inner-join implementation and a `NOT EXISTS` implementation are both consistent
  with the current wording but produce different audiences. **Action required** (Phase 2): define
  `has_not` explicitly as requiring an *existing* `CampaignRecipient` row for the referenced
  campaign with the relevant timestamp column null — i.e., "was sent it and didn't open/click it,"
  not "wasn't sent it." Contacts never sent that campaign should not qualify as `has_not`.

- **[OPEN] The "data as of" indicator has no trustworthy timestamp to point at.** The schema adds
  engagement values but no successful-sync timestamp, and polling deliberately swallows per-item
  failures (matching the existing `poll_campaign_status` pattern). If refreshes fail silently for
  days, the UI has nothing but `completed_at` or the polling-window end to infer freshness from,
  and would present stale data as current. **Action required** (Phase 1): add
  `engagement_last_synced_at` (updated only after a fully successful refresh) and a fixed
  `engagement_polling_expires_at` to `Campaign`, and expose both through the API so the results UI
  can build an honest "data as of" indicator.

- **[OPEN] Claimed phase value contradicts the phase boundaries.** Further Notes below claims
  "Phase 2 alone already solves the original 'exclude prior openers' problem," but Phase 2
  explicitly excludes attaching/applying a segment to a campaign — that's Phase 3. As written,
  after Phases 1 and 2 ship, a user still cannot actually send a follow-up campaign restricted to
  a segment. **Action required**: either move `segment_id` and send-time segment resolution into
  Phase 2 (so `list_membership`/`campaign_activity` segments are usable end-to-end before
  `contact_field` conditions exist, with `contact_field` becoming the sole Phase 3 addition), or
  stop describing Phase 2 as independently solving the user-facing problem.

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
  openers" problem (and subsumes "target a specific list," via `list_membership`) even before
  contact-field conditions exist; Phase 3 completes the general filter engine and wires it into
  campaign sending. Phases can be re-sequenced or split further if needed, but this ordering was
  chosen to ship the original problem's solution (Phase 2) as early as possible.

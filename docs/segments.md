# Segments

A segment is a saved, reusable, rule-based filter over Looply's entire contact base. It defines a
campaign's audience — see [Campaigns](campaign.md). Full design history and rationale live in
`docs/prds/0001-campaign-segments.md`; this document describes the shipped shape.

## Scope

A segment is not owned by, or scoped to, any one contact list. "Is a member of list X" is just one
filterable condition among others (list membership, prior-campaign engagement), combinable with
AND/OR logic. There is no separate, required "base list" a segment narrows down — the common
"everyone in list X" case is just a segment with a single `list_membership` condition.

Phase 2 supports two leaf condition types: `list_membership` and `campaign_activity`.
`contact_field` conditions (company, contact type, location, etc.) are Phase 3.

## Segment data

| Field | Description |
| --- | --- |
| `id` | Looply segment ID |
| `name` | Unique across the account, not per-list |
| `rule` | The validated condition tree (see "Rule tree" below) |
| `created_by_id` | The user who created the segment |

There is deliberately no `contact_list_id` column: a segment's only relationship to a list is
through a `list_membership` condition inside its rule tree.

## Rule tree

`Segment.rule` stores a discriminated, depth/size-bounded Pydantic tree
(`app/schemas/segment_rule.py`) — not raw/free-form JSON. The API rejects (422) anything that
doesn't parse into this shape:

- `MAX_TREE_DEPTH = 5` — a `RuleGroup` nested inside a `RuleGroup` counts as +1 depth.
- `MAX_LEAVES = 25` — total leaf conditions anywhere in the tree.

A rule tree's root is either a single leaf condition or a `RuleGroup` (`op`: `and`/`or`,
`conditions`: a list of further leaves or groups).

### `list_membership`

```json
{"type": "list_membership", "list_id": "9c11...44ab", "op": "in"}
```

`op` is `in` or `not_in`. Resolved as an `EXISTS`/`NOT EXISTS` join against
`ContactListMember` filtered to `list_id`, requiring `deleted_at IS NULL` for `in`.

### `campaign_activity`

```json
{"type": "campaign_activity", "campaign_id": "3fa2...c9d1", "event": "opened", "op": "has_not"}
```

`event` is `opened` or `clicked`; `op` is `has` or `has_not`.

- **Lifecycle validation**: `campaign_id` must reference a campaign that exists and is
  `completed`, checked at segment create/update time (422 if not) and re-checked at every
  resolution (preview or send). A campaign deleted or reverted after the segment was saved fails
  the resolve explicitly, rather than silently matching every contact.
- **`has_not` semantics**: "was sent this campaign and did not open/click it" — requires an
  *existing* `CampaignRecipient` row for `campaign_id` with the relevant timestamp column null. A
  contact never sent that campaign does **not** satisfy `has_not`.

### Combining conditions

```json
{
  "op": "and",
  "conditions": [
    {"type": "list_membership", "list_id": "9c11...44ab", "op": "in"},
    {"type": "campaign_activity", "campaign_id": "7ab0...12ef", "event": "clicked", "op": "has"}
  ]
}
```

A rule tree with **zero** `list_membership` conditions is valid and resolves against the account's
entire contact base — this is intentional (see "Design note" below), mitigated by the preview
endpoint.

## Resolver

`app/repositories/segment_resolver.py` compiles a validated rule tree into a SQLAlchemy filter
against `Contact`/`ContactListMember`/`CampaignRecipient`. It exposes:

- `resolve_contacts_query(db, root)` — the segment's resolved `Contact` query.
- `resolve_count(db, root)` — the same compiled filter wrapped in `COUNT(*)`.

Both share one compiled-filter code path, so a segment's preview count and its actual send
audience can never independently drift. Neither result is persisted — `contact_count` is always
recomputed on demand.

## Endpoints

- `POST /segments`, `GET /segments`, `GET /segments/{id}`, `PUT /segments/{id}`,
  `DELETE /segments/{id}` — standard CRUD, following the existing soft-delete repository pattern.
  Top-level, not nested under `/contact-lists/{id}/...`.
- `GET /segments/{id}/preview` — `{"contact_count": int}` for a saved segment, computed live.
- `POST /segments/preview` — same shape, but accepts a raw rule tree body so the UI can show a
  live count while a segment is still being built/edited, before it's saved.

## Campaigns and segments

`Campaign.segment_id` is required: a campaign's audience is always "resolve this segment." At send
time, `CampaignRepository.get_eligible_recipients_for_segment()` intersects the segment's resolved
contact set with the same eligibility filter used before segments existed (active, has email,
deduplicated by email) — see [Campaigns](campaign.md#send-a-campaign).

## Design note

An earlier version of this design scoped every segment to exactly one `contact_list_id`, mirroring
Mailchimp's Audience-scoped segments. That was reconsidered because it forced a rigid two-step flow
(list, then segment-on-list) and made segments non-reusable across lists, even though
`ContactListMember` already supports many-to-many list membership. The current design (Loops.so-style:
list membership as just one filter condition) removes that rigidity at the cost of allowing a
segment to resolve to the entire contact base if built that way — an accepted trade-off, mitigated
by the non-persisted `contact_count` preview endpoint.

## Future work

- `contact_field` conditions (company, contact type, location, etc.) — Phase 3.
- A "pick a list" shortcut in the campaign-creation flow that transparently creates a trivial
  one-condition segment behind the scenes, so the common case stays as quick as picking a list.
- "Did not open **any** campaign" (as opposed to a specific named campaign) as a condition variant.

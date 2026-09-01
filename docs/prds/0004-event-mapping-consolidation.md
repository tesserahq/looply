# Event Mapping Consolidation

## Problem Statement

Configuring how an ingested event populates a Contact is unnecessarily error-prone and disconnected
from how operators actually think about the problem.

Today, tracking an event type (`TrackedEventType`) and mapping its payload fields onto a Contact
(`EventFieldMapping`) are two independent tables, and `EventFieldMapping.event_type` is a free-text
string repeated on every single attribute row — deliberately not a foreign key to
`TrackedEventType`. Configuring `com.mylinden.contact.updated` to fill in `first_name`, `last_name`,
and `city` means creating three separate `EventFieldMapping` rows, each retyping
`"com.mylinden.contact.updated"` by hand. A typo on any one of them silently creates an orphaned
mapping that never applies to anything, with no error surfaced anywhere.

Worse, `TrackedEventType` turns out to be inert on its own: an event type can be "tracked" with zero
field mappings, but ingestion still requires a resolved `is_identity_key` mapping before it will
create a `CustomEvent` row or touch a Contact at all (see
`docs/prds/0003-event-driven-contact-resolution.md`). A tracked event type with no identity mapping
configured produces nothing but a dropped-event log line — it's a second, separate registration step
that adds a typo surface without adding real functionality.

Operators think about this in terms of one event: "for `com.mylinden.contact.updated`, which field
identifies the contact, and which fields do I want filled in?" The current data model doesn't match
that mental model, and makes the common case (configuring several attributes for one event) the most
error-prone one.

## Solution

Collapse `TrackedEventType` and the flat `EventFieldMapping` list into one two-level structure:

- **`EventMapping`** — one row per `event_type` (unique). Holds `source` (what to stamp on
  `Contact.source` for auto-created contacts) and the identity configuration
  (`identity_target_field` + `identity_source_path`) directly as columns. Creating this row *is* what
  registers the event type — there is no separate tracking step.
- **`EventFieldMapping`** — a child row per non-identity attribute, scoped to its parent `EventMapping`
  by a foreign key instead of a repeated `event_type` string. No more free-text duplication, no more
  `is_identity_key` flag to misconfigure.

An operator now configures one event in one place: create the `EventMapping` (naming the event type,
its source, and how to identify the contact), then add as many child field mappings underneath it as
needed — each one picked from an existing, unambiguous parent, not retyped.

Unlike the mapping rows this replaces, both the parent's identity configuration and each child
attribute mapping become editable in place (PATCH) rather than delete-and-recreate-only. This is a
deliberate reversal of the immutability rule from `docs/prds/0002-contact-custom-fields-and-events.md`
and `docs/prds/0003-event-driven-contact-resolution.md`: it trades away the original guarantee that a
mapping's meaning never silently changes underneath already-processed events, in favor of making
correcting a misconfigured mapping (the exact problem this PRD exists to reduce) a normal edit instead
of a destructive operation. See "Further Notes" for the accepted risk.

## User Stories

1. As an operator, I want to configure one event type in a single place, so that I don't have to
   retype its `event_type` string once per attribute.
2. As an operator, I want to pick an event's attributes from a list scoped to that event, so that a
   typo can't silently create a mapping that never fires.
3. As an operator, I want an event's identity configuration (which field identifies the contact, and
   where its value comes from in the payload) to live in one obvious place, so that I don't have to
   hunt through a flat list of rows to find which one has `is_identity_key=True`.
4. As an operator, I want configuring an event's first mapping to be the only step required to start
   processing that event type, so that I don't have to separately "track" it first.
5. As an operator, I want to fix a wrong `source_path` on an existing attribute mapping without
   deleting and recreating it, so that correcting a typo is a one-step edit.
6. As an operator, I want to fix a wrong identity field or source path without deleting the whole
   event configuration (and every attribute mapping under it), so that correcting the most
   consequential setting isn't the most destructive one to fix.
7. As an operator, I want deleting an event's configuration to stop all of its attribute mappings in
   one action, so that I don't have to separately clean up orphaned child rows.
8. As a developer integrating via the host API, I want the same create/read/update/delete operations
   available for both the event-level and attribute-level configuration as the UI uses, so that I can
   automate event mapping setup without needing UI-only functionality.
9. As an operator, I want the existing safeguards (unrecognized `target_field` rejected, `custom_field`
   requiring an existing field definition, string/list length bounds) to keep applying to attribute
   mappings after this change, so that data-integrity guarantees aren't weakened by the restructuring.
10. As a developer reading the ingestion code, I want a single lookup ("does an `EventMapping` exist
    for this `event_type`?") to answer whether an event is processed at all, so that there's one source
    of truth instead of two tables that can disagree.

## Implementation Decisions

- **`EventMapping` model** (new, replaces `TrackedEventType`): `event_type` (unique among active
  rows, via the same partial-index pattern `TrackedEventType` used), `source` (nullable string),
  `identity_target_field` (nullable string, validated against `IDENTITY_KEY_TARGETS` —
  `external_id`/`email` — when set), `identity_source_path` (nullable string; set together with
  `identity_target_field` or not at all), `created_by_id`, standard timestamp/soft-delete mixins.
  Both identity columns are optional at creation — an `EventMapping` can exist with no identity
  configured yet, matching today's "tracked but no identity mapping" state, but ingestion still drops
  events for it exactly as it does today.
- **`EventFieldMapping` model** (modified): gains `event_mapping_id` (FK to `event_mappings.id`,
  required). Drops `event_type` (redundant with the parent's) and `is_identity_key` (redundant with
  the parent's identity columns). `target_type`, `target_field`, `field_definition_id`, `source_path`,
  `created_by_id` are unchanged. `CONTACT_FIELD_TARGETS` validation is unchanged.
- **`EventMappingRepository`** (new, replaces `TrackedEventTypeRepository`): create (uniqueness
  conflict on `event_type` → 409, same as today's `TrackedEventTypeConflictError`; invalid
  `identity_target_field` → 422), get-by-`event_type` (the ingestion-path lookup — replaces
  `TrackedEventTypeRepository.get_by_event_type` and doubles as the resolver's mapping-set lookup),
  update (identity fields and `source` are all editable; same validation as create applies to the new
  values), and delete (soft-deletes the parent and cascades a soft-delete to all of its currently
  active `EventFieldMapping` children in the same operation).
- **`EventFieldMappingRepository`** (modified): CRUD scoped by `event_mapping_id`. Create keeps the
  existing `target_field`/`target_type` shape validation
  (`InvalidEventFieldMappingError`). The duplicate-identity-key check and
  `DuplicateIdentityKeyError` are removed entirely — identity is now a parent-level concept that
  can't structurally have more than one value. Gains an update method (source_path/target_type/
  target_field/field_definition_id are all editable in place); update re-runs the same shape
  validation create does.
- **`EventMappingResolver`** (existing deep module, `app/services/event_mapping_resolver.py`):
  signature changes from `resolve(mappings: list[EventFieldMapping], event_data: dict)` to accept the
  `EventMapping` parent (for identity) plus its active children (for attributes) — e.g.
  `resolve(event_mapping: EventMapping, field_mappings: list[EventFieldMapping], event_data: dict)`.
  Internal dot-path resolution logic (`extract_by_path`) and the `ResolvedEventMappings` result shape
  are unchanged. Remains dependency-free — no DB session, no model writes.
- **`process_nats_event_task`** (modified): replaces the `TrackedEventTypeRepository.get_by_event_type`
  "is this tracked" check with `EventMappingRepository.get_by_event_type` — no `EventMapping` row for
  this `event_type` is the new "drop, untracked" case (folding what were two lookups into one).
  Everything downstream of a found `EventMapping` (fetch its active children, resolve, get-or-create
  Contact, record `CustomEvent`, apply custom field values) is unchanged in behavior.
- **Routers/schemas**: `tracked_event_type.py` router is removed. A new `event_mapping.py` router
  exposes `POST`/`GET`/`GET {id}`/`PATCH {id}`/`DELETE {id}` on `/event-mappings` for the parent.
  `event_field_mapping.py` is restructured as a nested sub-resource under
  `/event-mappings/{event_mapping_id}/fields`, with the same HTTP verbs, scoped to that parent.
  `EventFieldMappingCreateRequest` drops `event_type` (now implied by the URL path) and
  `is_identity_key` (moved to `EventMappingCreateRequest`/`EventMappingUpdateRequest` as
  `identity_target_field`/`identity_source_path`). New `EventFieldMappingUpdateRequest` and
  `EventMappingUpdateRequest` schemas support the in-place edits described above.
- **RBAC**: collapses to a single resource, `looply.event_mapping`, covering create/read/update/delete
  on both the parent and its child field rows — replacing the two separate resources
  `looply.tracked_event_type` and `looply.event_field_mapping`.
- **`Contact.source`**: unchanged in meaning (stamped from the resolved `EventMapping.source` on
  auto-create); only the column it's read from moves from `TrackedEventType.source` to
  `EventMapping.source`.
- **Migration**: clean-slate — no production data exists in `tracked_event_types` or
  `event_field_mappings` today, so the migration drops `tracked_event_types`, creates
  `event_mappings`, and alters `event_field_mappings` (add `event_mapping_id` FK, drop `event_type`
  and `is_identity_key`) without a data-preserving backfill step.

## Testing Decisions

Good tests here exercise externally observable behavior — the shape of a request/response, what gets
written to the DB, what a pure function returns for a given input — not internal call sequences.

- **`EventMappingResolver`**: the highest-value target — a pure, dependency-free function, cheapest to
  test exhaustively. Cover: identity resolves/doesn't resolve (missing path, no identity configured on
  the parent), a mix of `contact_field` and `custom_field` children resolving independently, a child
  whose `source_path` doesn't resolve for this payload being skipped without affecting siblings.
  Follows the existing test style already in place for this module (no DB, no model writes, plain data
  in/out).
- **`EventMappingRepository`**: create-conflict (duplicate active `event_type` → 409), invalid
  `identity_target_field` → 422, update changing identity/source fields, and — most importantly for
  this PRD — delete cascading to soft-delete all active children in one call. Style follows
  `tests/app/repositories/test_contact_list_repository.py`.
- **`EventFieldMappingRepository`**: create shape-validation (unrecognized `target_field`, `custom_field`
  requiring an existing field definition), and the new update path (each editable column, plus that
  update re-validates the shape rather than accepting an inconsistent result).
- **Routers (`event_mapping.py`)**: HTTP-level tests for the parent CRUD, the nested `/fields`
  sub-resource CRUD, RBAC enforcement on the single consolidated `looply.event_mapping` resource, and
  the 404/409/422 error paths carried over from the current `event_field_mapping.py`/
  `tracked_event_type.py` router tests.
- **`process_nats_event_task`**: existing tests in `tests/app/tasks/test_process_nats_event_task.py`
  are updated to construct an `EventMapping` + children instead of a `TrackedEventType` +
  `EventFieldMapping` rows; behavioral coverage (untracked drop, no-identity drop, contact-field-only-
  on-create, custom-field-every-time) is unchanged in intent.

## Out of Scope

- **A single composite create/update endpoint** for configuring an event and all its attributes in one
  request was considered and rejected in favor of separate nested CRUD (`/event-mappings` and
  `/event-mappings/{id}/fields` as independent resources) — more REST-conventional, at the cost of the
  UI needing multiple calls to fully configure one event. Revisit if that orchestration proves painful
  in practice.
- **Backfilling/migrating existing `tracked_event_types`/`event_field_mappings` data** — not needed;
  no production data exists in either table yet.
- **Re-adding immutability, or any versioning/audit trail on mapping edits** — explicitly dropped in
  favor of in-place editability (see "Further Notes" for the accepted trade-off). A future PRD could
  revisit an audit log if the risk below proves costly in practice.
- **Changing ingestion's contact-field-only-on-create / custom-field-every-time asymmetry** — unrelated
  to this restructuring; carried over unchanged from `docs/prds/0003-event-driven-contact-resolution.md`.
- **A UI mockup** — this PRD is backend/data-model and API-contract only, same boundary 0001/0002/0003
  draw.

## Further Notes

- **Accepted risk of editable identity.** `docs/prds/0002-contact-custom-fields-and-events.md` and
  `docs/prds/0003-event-driven-contact-resolution.md` made mappings immutable specifically so a
  mapping's meaning could never silently change out from under already-processed events — particularly
  for identity resolution, since it determines which Contact an event even belongs to. This PRD
  deliberately reverses that for both attribute and identity edits: past contacts resolved under an
  old `identity_target_field`/`identity_source_path` will silently disagree with events resolved after
  an edit, with no record that the meaning changed. This is an intentional trade-off (a misconfigured
  mapping is now a one-step fix instead of a destructive delete-and-recreate), not an oversight — but
  it compounds with the pre-existing behavior that `custom_field` values already get silently
  overwritten on every matching event. If this proves to cause real confusion in practice (e.g.
  "why did this contact's identity field change retroactively"), the next step would be an audit log
  on `EventMapping`/`EventFieldMapping` edits, not re-introducing immutability.
- **`TrackedEventType` was already inert without an identity mapping.** This PRD's consolidation is
  possible specifically because `TrackedEventType` never did anything on its own — ingestion's
  `has_identity` check already gates every downstream effect (Contact resolution, `CustomEvent`
  creation) on a resolved identity mapping, regardless of whether the event type was "tracked." An
  `EventMapping` row with no identity configured yet behaves identically to today's "tracked, no
  identity mapping" state: it exists, but ingestion drops every event for it until identity is added.

# Event-Driven Contact Resolution and Provenance

## Problem Statement

Looply's NATS event ingestion (`docs/prds/0002-contact-custom-fields-and-events.md`) resolves and
auto-creates a `Contact` by reading a fixed `user` object off the top level of every incoming
envelope. In production, this is silently broken: real envelopes from Linden (`com.mylinden.*`
events) carry no top-level `user` object at all — `user` lives nested inside `event_data.user`,
alongside sibling objects like `event_data.person` and `event_data.account`. Every such event is
dropped with `"Dropping NATS event with no embedded user.id"`, and nothing downstream (no Contact,
no CustomEvent, no field mapping) ever runs for it.

Even once that path mismatch is fixed, reading `event_data.user` is itself the wrong contact
identity for many event types. `com.mylinden.person.updated` describes an update to a *person*
(e.g. a family member) made by a *user* (e.g. the account owner) — today's design would resolve
every such event to the acting user's contact, so ten family members created by one account owner
all collapse onto a single Contact instead of ten. There's no way to say "for this event_type, the
contact is `event_data.person`, not `event_data.user`."

Finally, Looply has no way to tell, for a given Contact, whether it was created by a human operator,
imported, or auto-created from an event — and if from an event, from which channel (Linden vs. some
future host, or a finer distinction like "website" vs. "phone"). This blocks any operator workflow
that needs to filter or audit contacts by how they entered the system.

## Solution

Extend the `EventFieldMapping` primitive introduced in 0002 (currently: `event_type` + `source_path`
→ a `CustomFieldDefinition`) so a single mapping table drives all three needs:

- **Which built-in Contact field a payload path fills** (`first_name`, `last_name`, `email`, etc.),
  not just custom fields — via a `target_type` discriminator (`contact_field` | `custom_field`).
- **Which one mapping identifies the contact** for a given `event_type` — via an `is_identity_key`
  flag on exactly one mapping per `event_type`, targeting either `external_id` or `email`. This lets
  an operator configure `com.mylinden.person.updated` to resolve/create contacts from
  `event_data.person.id`, while a different event_type could resolve from `event_data.user.id`
  instead — no more hardcoded assumption about which sub-object is "the" identity.
- **Where a value comes from at all** — dot-paths are now resolved against the same `event_data`
  dict for every mapping (contact-field or custom-field), fixing the top-level `user` mismatch as a
  side effect of making the source path fully configurable instead of hardcoded.

Separately, add a `Contact.source` column (free-form string: `manual`, `website`, `phone`,
event-derived values, etc.) and a matching `TrackedEventType.source` column — every contact
auto-created from a given `event_type` is stamped with that event_type's registered `source`,
answering "was this contact created by an event, and which channel" without overloading the
existing, user-editable `Tag`/`ContactTag` mechanism for it.

## User Stories

1. As a Linden platform engineer, I want Looply to correctly resolve `user.id` regardless of whether
   it's nested under `event_data` or elsewhere in the envelope, so that events aren't silently
   dropped due to a hardcoded path assumption.
2. As a Looply operator, I want to configure, per `event_type`, which payload path identifies the
   contact (e.g. `event_data.person.id` vs. `event_data.user.id`), so that events about a different
   subject than the acting user resolve to the right Contact instead of collapsing onto one.
3. As a Looply operator, I want to configure that identity lookup to key off either `external_id` or
   `email`, so that event types without a stable external id can still resolve contacts by email.
4. As a Looply operator, I want an event_type's identity-key mapping to be the single source of
   truth for both finding an existing Contact and creating a new one, so that there's no ambiguity
   about which of several sub-objects in a payload "is" the contact.
5. As a Looply operator, I want to map any payload path onto a built-in Contact field
   (`first_name`, `last_name`, `email`, `phone`), not just custom fields, so that I don't need a
   custom field definition just to populate ordinary contact attributes from an event.
6. As a Looply operator, I want to be prevented from creating a second identity-key mapping for an
   event_type that already has one, so that ingestion behavior for that event_type stays
   unambiguous.
7. As a Looply operator, I want an event whose configured identity-key path resolves to nothing (or
   whose event_type has no identity-key mapping at all) to be dropped and logged, exactly like
   today's fail-safe behavior, so that no event is ever misfiled onto the wrong contact.
8. As a Looply operator, I want every Contact to record a `source` (e.g. `manual`, `website`,
   `phone`, or an event-derived value), so that I can tell how a contact entered the system.
9. As a Looply operator, I want contacts auto-created from a tracked event_type to be stamped with
   that event_type's configured source, so that I don't have to configure source per-mapping on top
   of everything else.
10. As a Looply operator, I want `Contact.email` to be unique when present, so that email can safely
    be used as an identity-key lookup without silently matching or creating duplicates.
11. As a developer running the migration that adds the email uniqueness constraint, I want it to
    fail loudly and list any pre-existing duplicate emails rather than silently mutate contact data,
    so that data cleanup stays a deliberate, reviewed human action.
12. As a developer maintaining Looply, I want the envelope-parsing/identity-resolution logic
    isolated in a single pure module (no DB, no Celery), so that its branching (contact-field vs.
    custom-field, identity vs. non-identity mapping, missing path) is unit-testable without spinning
    up ingestion infrastructure.
13. As a developer maintaining Looply, I want existing `EventFieldMapping` rows created under 0002
    (custom-field-only) to keep working unchanged after this migration, so that shipping this PRD
    doesn't silently break already-configured custom field ingestion.

## Implementation Decisions

### `EventFieldMapping` extension

- Add `target_type: Enum('contact_field', 'custom_field')`, not nullable. Migration backfills every
  existing row to `'custom_field'` (the only kind that existed under 0002), preserving current
  behavior unchanged.
- Add `target_field: str | None` — a Contact column name (`first_name`, `last_name`, `email`,
  `phone`, `external_id`, etc.), required and only meaningful when `target_type='contact_field'`.
  Validated against a fixed allow-list of real, settable Contact columns at write time (422 on an
  unrecognized name) — not a free string, to avoid a typo silently becoming a no-op mapping.
- `field_definition_id` becomes nullable — required when `target_type='custom_field'`, must be null
  when `target_type='contact_field'`. Enforced at the repository/service layer (a DB check
  constraint is acceptable too, at implementer's discretion) rather than only at the Pydantic layer,
  since this is a cross-field invariant.
- Add `is_identity_key: bool`, default `False`. Only valid when `target_type='contact_field'` and
  `target_field` is `external_id` or `email` — rejected (422) otherwise. `create_mapping` checks that
  no other active mapping for the same `event_type` already has `is_identity_key=True` before
  inserting; violating this is rejected (409), not silently allowed as a second candidate.
- `source_path` semantics are unchanged (dot-path resolved against `event_data`) — every mapping,
  identity or not, contact-field or custom-field, is resolved the same way.
- Everything else about the model (immutable once created, soft-deletable, `created_by_id`
  semantics) carries over from 0002 unchanged.

### `EventMappingResolver` (new module)

A new, dependency-free module (e.g. `app/services/event_mapping_resolver.py`) that takes the list of
`EventFieldMapping` rows for an `event_type` plus the envelope's `event_data` dict, and returns a
small result object with:
- `identity_field: Literal["external_id", "email"] | None` and `identity_value: str | None` — from
  the single `is_identity_key=True` mapping, or both `None` if that mapping's path didn't resolve or
  no such mapping exists for the event_type.
- `contact_field_values: dict[str, Any]` — every resolved non-identity `contact_field` mapping.
- `custom_field_values: dict[str, Any]` — every resolved `custom_field` mapping (by field name, as
  today).

This is a pure function over plain data — no DB session, no model imports beyond the mapping rows
already fetched by the caller. It replaces the logic currently split between `_process_nats_event`
(the hardcoded `user` read) and `_apply_field_mappings` in `process_nats_event_task.py`.

### `process_nats_event_task.py` changes

- `_process_nats_event` fetches `EventFieldMappingRepository.get_mappings_for_event_type(event_type)`
  once, passes it and `event_data` to `EventMappingResolver`, and uses the result to drive
  everything downstream — the current hardcoded `msg.get("user")` read is deleted entirely.
- If `identity_value` is `None` (unresolved path or no identity-key mapping configured), log and
  drop the event exactly as today's "no embedded user.id" case does — same fail-safe behavior, just
  driven by configurable mappings instead of a fixed path.
- `raw_envelope`/`CustomEvent` recording is unchanged.

### `ContactRepository` changes

- `get_or_create_from_event_user` is replaced by a more general
  `get_or_create_from_event(identity_field, identity_value, contact_field_values, source)`:
  - Looks up an existing contact by `external_id` or `email` depending on `identity_field`.
  - On a known match, identity/attribute fields are still never overwritten from event data — same
    "operator corrections win" rule as 0002.
  - On no match, creates a new `Contact` with `contact_field_values` applied (whichever of
    `first_name`/`last_name`/`email`/etc. were resolved), `external_id` or `email` set per
    `identity_field`/`identity_value`, and `source` stamped from the caller.

### `Contact.source` / `TrackedEventType.source`

- Add `Contact.source: str | None` — free-form string, no enum (operators may want values beyond
  what ships today, e.g. `manual`, `website`, `phone`, and per-event-type values like `linden`).
  Existing contacts get `NULL` (unknown/pre-dates this column); Looply's own manual-create flow sets
  `source='manual'` explicitly going forward.
- Add `TrackedEventType.source: str | None` — the constant stamped onto every contact auto-created
  while ingesting that event_type. Nullable so existing `TrackedEventType` rows (from 0002) don't
  need a value before this ships; a `NULL` source event_type simply stamps `Contact.source=None` on
  auto-create, same as today's implicit behavior.

### Email uniqueness

- Add a partial unique index on `Contact.email` (`WHERE email IS NOT NULL`), mirroring the existing
  `external_id` partial-index pattern from 0002, so `email` is safe to use as an identity-key lookup
  target.
- The migration runs a pre-check query for duplicate non-null emails first and aborts with a clear
  error listing the offending emails if any are found — no automatic mutation of existing contact
  data. A human resolves duplicates (merge or clear) before re-running the migration.

## Testing Decisions

Good tests here exercise external behavior — "given this event_type's mappings and this
`event_data`, what does the resolver return" / "given this envelope, what contact and event
result" — not internal call sequencing, matching 0001/0002's existing standard.

- **`EventMappingResolver`** is the module most worth isolating and testing thoroughly, per the
  user's explicit request — it's a pure function, no DB/Celery/NATS needed:
  - A `contact_field` mapping resolves its `source_path` into `contact_field_values` under the right
    key.
  - A `custom_field` mapping resolves into `custom_field_values` under the field's name, unchanged
    from 0002's existing behavior.
  - The `is_identity_key=True` mapping's resolved value becomes `identity_value`/`identity_field`,
    and is *not* duplicated into `contact_field_values`.
  - A missing `source_path` (any mapping) is skipped, not an error — mirrors 0002's existing
    "missing path → skip" rule.
  - No identity-key mapping present for the event_type → `identity_field`/`identity_value` are both
    `None`.
  - Multiple non-identity mappings of mixed `target_type` for the same `event_type` all resolve
    independently in one call.
- **Event ingestion Celery task** (`_process_nats_event`, called directly with a plain dict as
  today, no live NATS needed):
  - A `com.mylinden.person.updated`-shaped envelope with `event_data.person.id` configured as the
    identity key creates/resolves a Contact keyed on `person.id`, not `event_data.user.id` — the
    regression test for the original bug.
  - An event whose identity-key path doesn't resolve is dropped and logged, no Contact/CustomEvent
    row created.
  - A newly auto-created contact is stamped with its `event_type`'s `TrackedEventType.source`.
  - A second event for an already-known identity value never overwrites existing contact-field
    values (unchanged from 0002).
  - Identity key configured as `email` resolves/creates by `Contact.email` instead of
    `external_id`.
- **`EventFieldMappingRepository.create_mapping`**:
  - Creating a second `is_identity_key=True` mapping for an `event_type` that already has one is
    rejected (409).
  - `is_identity_key=True` with `target_field` other than `external_id`/`email` is rejected (422).
  - `target_type='contact_field'` with a `field_definition_id` set, or `target_type='custom_field'`
    with `target_field` set, is rejected (422).
  - `target_type='contact_field'` with an unrecognized `target_field` name is rejected (422).
- **Migration tests / a manual pre-deploy check**: verify the duplicate-email pre-check query
  correctly identifies known-duplicate fixtures and aborts before the index is added.

Ask the user which of these (beyond `EventMappingResolver`, already confirmed) they want tests
written for before implementation begins.

## Out of Scope

- **Retroactive backfill of contacts already created via the old hardcoded `user` path** — this PRD
  fixes ingestion going forward only. Whether any real (non-test) contacts were miscreated by the
  bug is a separate data-cleanup task, not addressed here.
- **Reconciling `Contact.source` with the `Tag`/`ContactTag` mechanism** (prototyped alongside this
  work on `feat/custom-events-nats-ingestion`) — `source` is a single system-stamped provenance
  field; tags remain a separate, user-editable, multi-value labeling mechanism. No migration of one
  into the other, and no UI-level unification, is designed here.
- **Wildcard or pattern-based `event_type` matching** for `EventFieldMapping` — exact match only,
  unchanged from 0002.
- **Event-to-field aggregation/counting** (e.g. auto-incrementing a count field from repeated
  events) — unchanged "explicitly out of scope" from 0002; this PRD only makes single-value
  path-extraction more flexible, not aggregation-capable.
- **A UI for configuring `target_type`/`is_identity_key`/`target_field`** — this PRD is
  backend/data-model and API-contract only, same boundary as 0001/0002.
- **Multi-host source namespacing** — `source` is a free string with no per-host prefixing
  convention; same single-tenant assumption 0002 documents for field/event names.

## Further Notes

- The originally observed failure (`"Dropping NATS event with no embedded user.id"` for a real
  `com.mylinden.person.updated` event) is explained precisely by this PRD's Problem Statement: the
  production envelope nests `user` under `event_data.user`, not at the envelope's top level as
  0002's example envelope assumed. This PRD's fix is generalization (configurable source paths),
  not a one-line path correction, because the same investigation surfaced the deeper "wrong sub-object
  becomes the contact" issue as a design gap, not just a typo.
- Before implementation, an operator must configure, at minimum, one identity-key `EventFieldMapping`
  for every currently-tracked `event_type` (e.g. `com.mylinden.person.updated` →
  `event_data.person.id` as `external_id`) — without it, those event types will start being dropped
  under the new logic exactly as they are being dropped today, just for a documented reason instead
  of a bug.

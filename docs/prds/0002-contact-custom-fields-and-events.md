# Contact Custom Fields and Events

## Problem Statement

Looply is part of the Linden platform, but today it has zero visibility into data owned by other
Linden services. A Looply `Contact` is just email/name/company/location — there's no link back to
a Linden account, and no way to know anything about what that account has *done* or *has*: whether
it has added a family member, whether it owns a pet, whether it has completed onboarding. This
blocks an entire category of campaign targeting the business actually wants — e.g. "email everyone
who signed up but hasn't added a family member yet" — which today is impossible without manually
cross-referencing Linden's own admin tools contact-by-contact.

At the same time, Looply is explicitly meant to be usable beyond Linden — a tool that could plug
into a different host platform later. If "family member" or "pet" become first-class Looply
concepts (dedicated columns, dedicated condition types), every future host integration requires a
new Looply schema change, and Looply stops being platform-agnostic in practice even if it claims to
be in principle.

## Solution

Two generic, host-agnostic extensibility primitives — the same shape Mailchimp and Loops.so use to
let any integrating application extend a contact without the sending platform needing to understand
what the data means:

- **Custom Fields**: explicitly typed, named key/value attributes on a contact (e.g.
  `family_member_count: 2`). The type is declared once, explicitly, when the field is *defined* —
  never inferred from a value — either by an operator through Looply's UI, or by a host platform
  through the API. Once defined, every value written for that field name must match the declared
  type or is rejected.
- **Custom Events**: an append-only per-contact log of named occurrences (e.g. `person.created`),
  each with a timestamp and an arbitrary JSON properties payload. Events are ingested through a
  dedicated endpoint that accepts the CloudEvents-shaped envelope Linden's own services already
  emit internally (`spec_version`, `source`, `event_type`, `event_data`, `time`, `labels`, `tags`,
  `user`) — Looply extracts the handful of fields it needs generically and never needs to
  understand what any given `event_type` or `event_data` shape means.

Fields and events are deliberately **independent** primitives with no automatic derivation between
them — recording a `person.created` event never automatically increments a `family_member_count`
field. A host that wants both keeps them in sync itself. This keeps Looply's own logic simple and
avoids Looply needing to understand event semantics (what does "created" imply for a given field?)
that are inherently host-specific.

Contact identity is resolved through a new `Contact.external_id` column. Every ingested event
carries a `user` object (`id`, `email`, `first_name`, `last_name`) inside its envelope; on an
event referencing a `user.id` Looply hasn't seen before, Looply upserts a new `Contact` from that
data rather than requiring some separate sync step to have run first and dropping/queuing the
event until it has.

Once this lands, Looply's segment rule tree (`docs/prds/0001-campaign-segments.md`, Phase 2) gains
two new leaf condition types — `custom_field` and `custom_event` — so a segment can express "has
not recorded a `person.created` event" or "`family_member_count == 0`" the same way it already
expresses `list_membership` or `campaign_activity`. This PRD does not modify 0001's existing leaf
types; it only adds the two new ones its own design already anticipated a slot for.

## User Stories

1. As a Linden platform engineer integrating with Looply, I want to define a new custom field with
   an explicit name and type via API, so that I can start writing `family_member_count` values for
   contacts without a human having to create it in Looply's UI first.
2. As a Looply operator, I want to define a new custom field with an explicit name and type through
   Looply's UI, so that I can prepare a field for use (e.g. ahead of a campaign I'm planning) without
   needing an engineer to make an API call.
3. As a Looply operator, I want to browse the list of known custom field definitions (name, type,
   who created it, when), so that I understand what data is available to filter campaigns on before
   I build a segment.
4. As a Looply operator, I want to see a given contact's current custom field values and who/what
   last set each one (a specific host integration, or a named operator), so that I can debug why a
   contact does or doesn't match a segment.
5. As a Looply operator, I want to manually correct or delete a contact's custom field value, so
   that I can fix bad data from a host integration without waiting on an engineer.
6. As a Looply operator, I want to delete a custom field definition that's no longer useful, so that
   the list of fields available when building a segment stays relevant, with its values removed
   along with it.
7. As a Linden platform engineer, I want to write/update a contact's custom field value via a single
   API call keyed by our own account/user id, so that I never need to look up or store Looply's
   internal contact UUIDs.
8. As a Linden platform engineer, I want a field value write rejected with a clear error if it
   doesn't match that field's declared type, so that a bug on our side fails loudly instead of
   silently corrupting segment results.
9. As a Linden platform engineer, I want to forward our own domain events (e.g.
   `com.mylinden.person.updated`) to Looply close to as-is, so that I don't have to build and
   maintain a separate translation layer just to keep Looply in sync with what already happened.
10. As a Linden platform engineer, I want an event addressed to a user Looply hasn't seen before to
    still succeed (auto-creating that contact from the event's embedded user info), so that event
    ingestion has no ordering dependency on some other contact-sync process running first.
11. As a Looply operator, I want to browse a contact's custom event history (name, timestamp,
    properties), so that I can verify integration data is flowing correctly.
12. As a campaign sender, I want to build a segment condition on a custom field (e.g.
    `family_member_count == 0`) or a custom event (e.g. has not recorded `person.created`), so that
    I can target campaigns using data Looply doesn't own itself.
13. As a developer maintaining Looply, I want custom fields and custom events to be fully
    independent of any specific host platform's vocabulary, so that plugging Looply into a second
    host platform later requires zero Looply schema or code changes — only that host calling the
    same generic API.
14. As a developer maintaining Looply, I want field-value writes and event ingestion authenticated
    through the API-key mechanism that already exists, so that this doesn't introduce a second,
    parallel auth system to maintain.

## Implementation Decisions

### Identity: `Contact.external_id`

- Add `external_id: str | None` to `Contact` (nullable, unique, indexed) — mirrors the existing
  `User.external_id` pattern (from `tessera_sdk`'s `UserMixin`) already used to tie a Looply `User`
  to its Linden platform identity. Nullable because existing contacts created through Looply's own
  UI/import flow have no external system to reference.
- Resolution is upsert-on-write, from two different entry points with two different payloads:
  - **Field value writes** take `external_id` directly as a path/body parameter (the host already
    knows its own id; no envelope involved) — if no `Contact` with that `external_id` exists, the
    write is rejected (404). Field writes don't carry enough contact info (no email/name) to safely
    auto-create a contact.
  - **Event ingestion** carries a `user` object (`id`, `email`, `first_name`, `last_name`) inside
    the CloudEvents envelope. On an event whose `user.id` has no matching `Contact.external_id`,
    Looply creates one from that data (`external_id = user.id`, `email`, `first_name`,
    `last_name`). On a *known* `external_id`, event ingestion never overwrites the existing
    contact's identity fields — only Looply's own contact-edit flows do — so events can't silently
    clobber a name/email an operator has since corrected.

### Custom Fields

- **New model** `CustomFieldDefinition` (new file, e.g. `app/models/custom_field_definition.py`),
  following existing model conventions (`TimestampMixin`, `SoftDeleteMixin`, UUID PK,
  `created_by_id: UUID | None` — null when created by a host API call, set to the operator's user
  id when created through the UI):
  - `name: str`, unique (case-insensitive) across the deployment — single-tenant, so no
    per-host namespacing is needed (see "Out of Scope").
  - `value_type: FieldValueType` — an enum (`STRING`, `NUMBER`, `BOOLEAN`, `DATE`), **required at
    creation, never inferred from a value**. Immutable once set — changing a field's type after
    values already exist under it would make those values incomparable; a definition must be
    deleted and recreated instead.
  - `label: str | None` — optional human-readable display name for the operator UI, separate from
    the machine `name`.
- **New model** `ContactCustomFieldValue`:
  - `contact_id: UUID` (FK to `contacts.id`), `field_definition_id: UUID` (FK to
    `custom_field_definitions.id`), unique together — one current value per contact per field
    (writing again overwrites, it does not append; this is current-state data, not a log).
  - `value: JSONB` — the actual value, validated against the field's `value_type` on every write.
  - `set_by: SetBySource` — a small discriminated value recording provenance: either the calling
    host's identity (from the API-key principal) or the operator's user id, so "who/what last set
    this" (user story 4) is always answerable without a separate audit log.
- **Write endpoint**: setting `/contacts/{external_id}/custom-fields/{field_name}` to a value is a
  single upsert call, usable by both a host (API key) and an operator (Looply UI, same endpoint,
  different caller identity) — collapsing "host writes" and "operator manual correction" into one
  code path rather than two, since the only real difference between them is *who* is calling, which
  `set_by` already captures.
  - Writing to an undefined `field_name` is rejected (422) — the definition must exist first
    (created by either an operator or a host, per user stories 1–2). No auto-creation of
    definitions from a bare value write, since that's exactly the inference behavior this PRD
    deliberately rejected.
  - Writing a value that doesn't match the field's locked `value_type` is rejected (422) with a
    clear message naming the expected type (user story 8).
- **Definition CRUD**: create (operator UI or host API, `value_type` required), list, soft-delete
  (cascades to hide that field's values — a deleted definition's data stops appearing in a
  contact's field list and stops being resolvable by segments, without a separate cleanup step).
  Renaming a definition's `name` after creation is out of scope — treated as immutable alongside
  `value_type`, for the same "already-written data references it" reason.
- **Read endpoints**: list a contact's current custom field values (with each value's `set_by`),
  and delete a single value (operator correction, user story 5) — distinct from deleting the
  definition itself (user story 6).

### Custom Events

- **New model** `ContactCustomEvent` (append-only — no update, no upsert-by-name; every ingested
  event is its own row):
  - `contact_id: UUID` (FK to `contacts.id`)
  - `name: str` — taken from the envelope's `event_type` (e.g. `com.mylinden.person.updated`).
    Free-form, no pre-registration/definition required (unlike fields) — there's no type to lock,
    so there's nothing that needs declaring upfront for correctness. The operator UI derives a
    browsable list of distinct event names from what's actually been recorded (user story 11),
    rather than from a separate definitions table.
  - `occurred_at: datetime` — from the envelope's `time`.
  - `properties: JSONB` — from the envelope's `event_data`, stored as-is.
  - `raw_envelope: JSONB` — the full incoming envelope stored verbatim (including `source`,
    `spec_version`, `subject`, `labels`, `tags`), for audit/debugging even though only `name`,
    `occurred_at`, and `properties` are used for segment resolution today (see "Out of Scope").
- **Ingestion endpoint**: `POST /events`, singular and not nested under `/contacts/{external_id}`,
  since the contact is identified from the envelope's embedded `user.id`, not from the URL — a
  path parameter would be redundant with data already in the body. Accepts the CloudEvents-shaped
  envelope directly (per the "Event ingestion shape" decision below); Looply reads `event_type`,
  `time`, `event_data`, and `user` and ignores the rest of the envelope for processing purposes
  (still storing it in `raw_envelope`).
- **Event ingestion shape**: Looply's contract accepts the envelope close to verbatim rather than
  requiring the host to pre-translate it into a Looply-specific body. This was a deliberate
  trade-off: CloudEvents itself is a generic, host-agnostic spec (not a Linden-specific format),
  and Looply only ever reads a fixed, generic set of top-level fields from it (`event_type`,
  `time`, `event_data`, `user`) — it never parses or depends on `event_data`'s internal shape,
  which is genuinely host/event-type-specific and stays opaque. This removes a translation-layer
  build/maintenance burden on the host side (user story 9) at the cost of Looply's ingestion
  contract assuming future host platforms also emit a CloudEvents-like envelope; see "Out of
  Scope" for why this is an accepted, revisitable trade-off rather than a permanent constraint.
- **Read endpoint**: list a contact's event history (`name`, `occurred_at`, `properties`),
  optionally filtered by `name`, for the operator UI (user story 11).

### Auth

- Both the field-value write endpoint and the event ingestion endpoint sit behind Looply's
  existing `AuthenticationMiddleware` (already wired into every request, already supports
  `X-API-Key`/`Bearer ak_...` alongside user JWTs) — no new authentication mechanism. A new RBAC
  permission (e.g. `custom_data:write`, following `app/auth/rbac.py`'s existing
  permission-registration pattern) gates the write/ingest endpoints; a `custom_data:read`
  permission gates the list/browse endpoints operators use.
- No per-contact ownership check is added, because Looply has no tenant/project boundary today
  (`app/auth/rbac.py`'s `global_domain` already documents this) — the only meaningful question for
  this API is "is the caller allowed to write custom data at all," which the RBAC permission
  answers.

### Segment rule tree integration (forward reference to 0001)

- Once this PRD ships, 0001's `Leaf` union gains two more members, following the exact
  discriminated-enum pattern 0001's "Rule tree schema" section already establishes for
  `list_membership`/`campaign_activity`/`contact_field`:
  - `custom_field` — `{"type": "custom_field", "field_name": str, "operator": ContactFieldOp,
    "value": ...}`, resolved as a join against `ContactCustomFieldValue`/`CustomFieldDefinition`
    filtered by `field_name`, reusing the same operator enum and value-type-aware comparison logic
    0001 already defines for its own `contact_field` condition.
  - `custom_event` — `{"type": "custom_event", "event_name": str, "op": CustomEventOp}`, where
    `CustomEventOp` is `HAS`/`HAS_NOT` (mirroring `CampaignActivityOp`). Resolved as a join against
    `ContactCustomEvent` filtered by `name`. Per the "custom_event has_not semantics" decision
    below, `HAS_NOT` means simply "zero matching rows exist" — this condition type has none of
    0001's `campaign_activity.has_not` ambiguity, because there's no two-step "was a recipient row
    created, but the event didn't fire" structure to disambiguate; an event either was recorded or
    wasn't.
- This PRD does not implement that rule-tree change itself — it's 0001's Phase 2 (or a later
  phase) responsibility to add these two leaf types once this PRD's tables exist to query against.

## Testing Decisions

Good tests here exercise external behavior — "given this write request, what row results" /
"given this envelope, what contact and event result" — not internal call sequencing, following the
same standard 0001 already sets (`tests/app/repositories/test_campaign_repository.py`,
`tests/app/tasks/test_poll_campaign_status.py`).

- **`CustomFieldWriteService`** (or equivalent repository method) is the module most worth
  isolating and testing thoroughly — it holds all the type-locking business logic:
  - First write of a new field name with a valid `value_type` at definition time succeeds.
  - A write matching the field's locked type succeeds and overwrites the prior value.
  - A write with a mismatched type is rejected (422) and doesn't create/modify a row.
  - A write to an undefined `field_name` is rejected (422).
  - `set_by` correctly distinguishes a host (API key) write from an operator (UI) write.
- **Event ingestion** (task/service, sibling in spirit to 0001's polling-task tests):
  - A well-formed envelope for a known `user.id` creates a `ContactCustomEvent` row with correctly
    extracted `name`/`occurred_at`/`properties`, without modifying the existing contact's
    email/name.
  - A well-formed envelope for an unknown `user.id` upserts a new `Contact` (with the envelope's
    `user.email`/`first_name`/`last_name`) and then records the event against it.
  - A second event for an already-known `user.id` never overwrites that contact's identity fields,
    even if the envelope's `user.email` differs from what's stored (documents which one wins, since
    contacts can also be edited independently in Looply).
- **Repository-level CRUD tests** for `CustomFieldDefinition` (create/list/soft-delete, immutable
  `value_type`), following `tests/app/repositories/test_contact_list_repository.py`'s style.
- **Router tests** for the write, ingestion, and read/list endpoints, including the RBAC permission
  checks (`custom_data:write`/`custom_data:read`) and the 404 (unknown `external_id` on a field
  write)/422 (unknown field, type mismatch) error paths.

Ask the user which of these modules they want tests written for before implementation begins — as
with 0001, the type-locking write path is the highest-value module to get right first.

## Out of Scope

- **Event-to-field derivation/aggregation** — an event never automatically updates a field (e.g.
  `person.created` does not auto-increment `family_member_count`). A host that wants both writes
  both. Revisit as a separate PRD if this proves to be a recurring integration pain point.
- **Multi-host namespacing** for field/event names — Looply is single-tenant per deployment today
  (no project/tenant boundary exists anywhere in the codebase), so there's exactly one host writing
  custom data into any given Looply instance. If Looply is ever deployed to serve multiple host
  platforms from one instance, field/event name collisions become a real problem needing a
  namespacing convention (e.g. a `source` prefix) — not addressed here.
- **Bulk/batch write endpoints** — single-record endpoints only. A host backfilling a large
  existing dataset (e.g. 100k existing family members) loops single calls. Revisit if that proves
  too slow in practice.
- **Filtering segments by event *properties*** — 0001's `custom_event` condition (see
  "Implementation Decisions" above) only supports has/has-not *by event name*, not filtering on
  values inside `properties`/`event_data` (e.g. "clicked event where `event_data.plan == 'pro'`").
  `properties`/`raw_envelope` are stored for audit/debugging and future use, not queried by segment
  resolution in this PRD.
- **Editing or deleting individual custom events** — the event log is append-only; no update/delete
  endpoint. A field value, by contrast, is explicitly editable/deletable (see "Custom Fields"
  above) since it represents current state, not a historical log. Compliance-driven deletion (e.g.
  a GDPR erasure request) is not addressed here — presumably handled at the `Contact`-deletion
  level, out of this PRD's scope.
- **Renaming a field definition's `name` or changing its `value_type` after creation** — both are
  immutable once set; a definition must be deleted and recreated instead.
- **Committing permanently to the CloudEvents envelope shape as Looply's one-true ingestion
  contract** — accepting it directly (rather than requiring host-side translation first) was a
  deliberate near-term trade-off given Linden's services already emit it. If a future, meaningfully
  different host platform can't produce a CloudEvents-shaped envelope, revisit whether ingestion
  needs a pluggable adapter layer rather than a fixed envelope contract — not designed here.
- **A read/write UI mockup** — this PRD is backend/data-model and API-contract only, same
  boundary 0001 draws; the operator-facing screens described in the user stories are a separate
  frontend effort.

## Further Notes

- This PRD is the "separate project" 0001's own "Out of Scope" section already named ("A
  custom-fields/tags system on `Contact`... Adding tags is a separate project"), generalized
  further to cover events too, once the actual shape of Linden's platform events (CloudEvents-like,
  with an embedded `user` object) became clear during design.
- The example envelope this design is based on:
  ```json
  {
    "source": "/linden",
    "spec_version": "1.0",
    "event_type": "com.mylinden.person.updated",
    "event_data": {
      "person": { "id": "...", "account_id": "...", "first_name": "Harry", "..." : "..." },
      "account": { "id": "...", "name": "Linda Carter Family" }
    },
    "data_content_type": "application/json",
    "subject": "/persons/...",
    "time": "2026-08-29T01:54:07.442732",
    "tags": ["person_id:...", "account_id:..."],
    "labels": { "person_id": "...", "account_id": "..." },
    "user_id": "943fdcc2-...",
    "user": { "id": "943fdcc2-...", "email": "...", "first_name": "...", "last_name": "..." },
    "id": "cc618d7f-...",
    "created_at": "2026-08-29T01:54:07.486493"
  }
  ```
  Looply's ingestion endpoint only ever reads `event_type`, `time`, `event_data`, and `user` from
  this — `source`, `spec_version`, `subject`, `tags`, `labels`, and the envelope's own `id` are
  stored in `raw_envelope` for audit but not otherwise interpreted.
- The original motivating example — "campaign for users who haven't yet created a family
  member" — is expressible once this ships as a single `custom_event` segment condition:
  `{"type": "custom_event", "event_name": "com.mylinden.person.created", "op": "has_not"}` — no
  `custom_field` needed for that specific case, since a count isn't actually required to express
  "hasn't happened yet." Fields remain valuable for genuinely value-based conditions (e.g.
  `family_member_count >= 3` for a "large family" segment), which an event log alone can't express
  as cleanly.

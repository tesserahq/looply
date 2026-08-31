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
14. As a developer maintaining Looply, I want field-value writes authenticated through the API-key
    mechanism that already exists, so that this doesn't introduce a second, parallel auth system
    to maintain for that path. (Event ingestion, ingested over NATS rather than HTTP, has no
    per-message auth of its own — see "Auth" below for why that's a transport-level trust boundary
    instead.)

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
    per-host namespacing is needed (see "Out of Scope"). The uniqueness constraint is a **partial
    unique index on `lower(name)` WHERE `deleted_at IS NULL`**, not a plain column-level
    constraint — deliberately, since "delete and recreate" is this PRD's own stated fix for a
    typo'd `name` or wrong `value_type` (see immediately below), and a plain constraint would
    block exactly that. `Segment.name` (`app/models/segment.py`) has this same gap today
    (`UniqueConstraint("name", ...)`, not scoped to `deleted_at`) — a pre-existing bug this PRD
    doesn't fix, but must not repeat.
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
  - `set_by_user_id: UUID` — simply `request.state.user.id`, whatever Looply's existing
    `AuthenticationMiddleware` resolved the caller to (API key or JWT alike; both paths already
    populate `request.state.user` with the same shape). No attempt to distinguish "a host
    integration" from "an operator" via `service_account` or API-key metadata — that distinction
    was considered and dropped as unneeded complexity; "who/what last set this" (user story 4) is
    answered by whichever user id authenticated the write, full stop.
- **Write endpoint**: setting `/contacts/{external_id}/custom-fields/{field_name}` to a value is a
  single upsert call, usable by both a host (API key) and an operator (Looply UI, same endpoint,
  different caller identity) — collapsing "host writes" and "operator manual correction" into one
  code path rather than two, since the only real difference between them is *who* is calling, which
  `set_by_user_id` already captures.
  - Writing to an undefined `field_name` is rejected (422) — the definition must exist first
    (created by either an operator or a host, per user stories 1–2). No auto-creation of
    definitions from a bare value write, since that's exactly the inference behavior this PRD
    deliberately rejected.
  - Writing a value that doesn't match the field's locked `value_type` is rejected (422) with a
    clear message naming the expected type (user story 8). A `DATE` value is a date-only ISO 8601
    string (e.g. `"2026-08-30"`, no time/timezone component), validated with Python's
    `date.fromisoformat()`.
- **Definition CRUD**: create (operator UI or host API, `value_type` required), list, soft-delete
  (cascades to hide that field's values — a deleted definition's data stops appearing in a
  contact's field list and stops being resolvable by segments, without a separate cleanup step).
  Renaming a definition's `name` after creation is out of scope — treated as immutable alongside
  `value_type`, for the same "already-written data references it" reason.
- **Read endpoints**: list a contact's current custom field values (with each value's
  `set_by_user_id`), and delete a single value (operator correction, user story 5) — distinct from
  deleting the definition itself (user story 6).

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
- **Ingestion transport: NATS, not HTTP** — following the exact pattern `orcha`
  (`~/sites/linden-family/orcha`) already uses to consume the same Linden domain events, rather
  than a `POST /events` endpoint (an earlier version of this PRD's plan, dropped in favor of this):
  - A **new, separate long-running process** (`run_nats_worker.py`-equivalent, started by its own
    `start_nats_worker.sh`-equivalent, alongside — not instead of — the existing API and Celery
    beat/worker processes) runs a [FastStream](https://faststream.airt.ai/) app with a
    `faststream.nats.NatsBroker`, subscribed via JetStream to Linden's shared event stream
    (`orcha`'s `EVT_LINDEN`, config'd via `NATS_STREAM_NAME`) on the wildcard subject `com.>`
    (`NATS_SUBJECTS`), with a durable, Looply-specific queue group name (`NATS_QUEUE`, e.g.
    `looply_worker` — analogous to `orcha`'s `orcha_worker`) so Looply gets its own full copy of
    every message on the stream independent of what `orcha` or any other consumer does with it.
  - The subscriber handler does the minimum needed to acknowledge quickly: it dispatches the raw
    message dict to a new Celery task (mirroring `orcha`'s `process_nats_event_task`) via
    `.delay(msg)`, and all actual envelope parsing, `Contact` upsert, and `ContactCustomEvent`
    creation happens inside that task — decoupling the NATS ack from DB work, same rationale as
    `orcha`'s split between `run_nats_worker.py`'s handler and `process_nats_event_task`.
  - `NatsEventPublisher` (`tessera_sdk.infra.events.nats_router`, already used by Looply today for
    outbound publishing — e.g. `app/commands/contact/create_contact_command.py`) is
    publish-only in the currently pinned SDK version; it has no subscriber counterpart. The
    NATS-subscriber side (`NatsEventSubscriber`, `run_nats_worker.py`) is therefore new code in
    Looply itself, following `orcha`'s `app/messaging/nats_subscriber.py` shape rather than
    importing it from the SDK — promoting it into `tessera-sdk` later, once a second service needs
    the exact same subscriber wrapper, is a reasonable follow-up but not this PRD's job.
  - This is a materially bigger operational addition than an HTTP endpoint: a third process to
    deploy/monitor, plus JetStream stream/consumer configuration (`NATS_URL`, `NATS_ENABLED`,
    `NATS_QUEUE`, `NATS_SUBJECTS`, `NATS_STREAM_NAME`), all new settings for Looply
    (`app/config.py`) mirroring `orcha`'s.
  - No `POST /events` HTTP endpoint ships alongside this — NATS is the only ingestion path. A host
    that cannot speak NATS directly is out of scope for this PRD (see "Out of Scope").
- **Event ingestion shape**: unchanged from the transport switch — Looply's Celery task still
  reads the envelope close to verbatim rather than requiring a Looply-specific body, extracting the
  same fixed, generic set of top-level fields (`event_type`, `time`, `event_data`, `user`) and
  storing the rest in `raw_envelope`. This was a deliberate trade-off: CloudEvents itself is a
  generic, host-agnostic spec (not a Linden-specific format), and Looply never parses or depends on
  `event_data`'s internal shape, which is genuinely host/event-type-specific and stays opaque. This
  removes a translation-layer build/maintenance burden on the host side (user story 9) at the cost
  of Looply's ingestion contract assuming future host platforms also emit a CloudEvents-like
  envelope; see "Out of Scope" for why this is an accepted, revisitable trade-off rather than a
  permanent constraint.
  - **Auto-create still applies**: unlike `orcha`'s own event consumer (which only reads a plain
    `user_id` and tolerates it not resolving, presumably because `orcha`'s own `users` table is
    kept in sync through some other channel), Looply's task still reads the envelope's embedded
    `user` object (`id`/`email`/`first_name`/`last_name`) and upserts a `Contact` on an unknown
    `user.id`, exactly as originally designed (see "Identity: `Contact.external_id`" above and user
    story 10) — the object is present on the wire regardless of transport; `orcha` simply chooses
    not to use it. Looply has no equivalent separate contact-sync channel, which is the whole
    reason auto-create exists here.
- **Read endpoint**: list a contact's event history (`name`, `occurred_at`, `properties`),
  optionally filtered by `name`, for the operator UI (user story 11) — this stays a normal
  authenticated HTTP endpoint; only ingestion moves to NATS.

### Auth

- The field-value write endpoint (still HTTP) sits behind Looply's existing
  `AuthenticationMiddleware` (already wired into every request, already supports
  `X-API-Key`/`Bearer ak_...` alongside user JWTs) — no new authentication mechanism there. A new
  RBAC permission (e.g. `custom_data:write`, following `app/auth/rbac.py`'s existing
  permission-registration pattern) gates it; a `custom_data:read` permission gates the list/browse
  endpoints operators use (definitions, values, event history).
- **Event ingestion (NATS) has no per-message authentication at the Looply layer at all** — trust
  is established once, at the transport level: whatever can publish onto the shared `EVT_LINDEN`
  JetStream stream in the first place is already trusted, the same boundary `orcha`'s own consumer
  relies on. There is no per-event API-key/JWT check inside the NATS handler or the Celery task,
  and no RBAC permission applies to this path — `custom_data:write` only gates the HTTP field-value
  endpoint. If the NATS stream itself is ever reachable by an untrusted publisher, that's a
  problem for Linden's NATS deployment/ACLs to solve, not something this PRD's ingestion code
  can check per-message.
- No per-contact ownership check is added, because Looply has no tenant/project boundary today
  (`app/auth/rbac.py`'s `global_domain` already documents this) — the only meaningful question for
  the HTTP field-value write is "is the caller allowed to write custom data at all," which the RBAC
  permission answers.

### Segment rule tree integration (forward reference to 0001)

- Once this PRD ships, 0001's `Leaf` union gains two more members, following the exact
  discriminated-enum pattern 0001's "Rule tree schema" section already establishes for
  `list_membership`/`campaign_activity`/`contact_field`:
  - `custom_field` — `{"type": "custom_field", "field_name": str, "operator": ContactFieldOp,
    "value": ...}`, resolved as a join against `ContactCustomFieldValue`/`CustomFieldDefinition`
    filtered by `field_name`, reusing `ContactFieldOp` (0001) — including the four comparison
    operators (`>`/`>=`/`<`/`<=`) added to that shared enum by this PRD (see below).

  **JSONB comparison**: `ContactCustomFieldValue.value` is `JSONB`, storing values of different
  Python types depending on the field's `value_type` — `apply_filters`'s plain `column > value`
  (which works for `contact_field`'s ordinary typed SQL columns) does not work directly against a
  JSONB column holding, say, a number. The `custom_field` resolver therefore does its own cast
  before applying `apply_filters`'s operator-to-SQL mapping, branching on the looked-up
  definition's `value_type`:
  ```python
  CAST_BY_VALUE_TYPE: dict[FieldValueType, Callable[[ColumnElement], ColumnElement]] = {
      FieldValueType.STRING: lambda col: col.astext,
      FieldValueType.NUMBER: lambda col: col.astext.cast(Numeric),
      FieldValueType.BOOLEAN: lambda col: col.astext.cast(Boolean),
      FieldValueType.DATE: lambda col: col.astext.cast(Date),
  }
  # resolver: cast_value = CAST_BY_VALUE_TYPE[definition.value_type](ContactCustomFieldValue.value)
  # then apply_filters's OPERATORS[operator](cast_value, condition.value) as usual
  ```
  This is resolver-internal — it doesn't change `apply_filters` itself (still used as-is for
  `contact_field` and everywhere else), and doesn't change the wire contract (a `NUMBER` value is
  still sent/stored as a JSON number, `DATE` as an ISO date string per the "Custom Fields" section
  above).

  Unlike `contact_field`, `custom_field.field_name` is a free-form string resolved against a
  `CustomFieldDefinition` row at request time — `value_type` isn't known until that row is looked
  up, so operator/value-type compatibility can't be a static Pydantic-only check the way
  `ALLOWED_OPS_BY_FIELD` is for `contact_field`. Instead:

  - **Lifecycle validation, mirroring `campaign_activity.campaign_id`** (0001's Phase 2): on
    segment create/update, `custom_field.field_name` must reference an active (non-soft-deleted)
    `CustomFieldDefinition`, and `operator` must be in that definition's `value_type`'s allowed set
    below — both checked by a DB lookup, not the Pydantic model alone (422 otherwise). Re-validated
    at resolution time too (preview and send), so a definition deleted after the segment was saved
    fails the resolve explicitly instead of silently matching zero/every contact.
  - **`ALLOWED_OPS_BY_VALUE_TYPE`** — the `custom_field` equivalent of 0001's
    `ALLOWED_OPS_BY_FIELD`, keyed by `FieldValueType` instead of a fixed field name (since
    `custom_field`'s "field" is dynamic, this is the one place the allow-list can live):
    ```python
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
    ```
    This is what makes the PRD's own motivating "large family" example (`family_member_count >=
    3`, see "Further Notes") expressible — `GTE` didn't exist on `ContactFieldOp` before this PRD;
    it's added to the shared enum specifically for `NUMBER`/`DATE` custom fields, since none of
    0001's own `contact_field` columns are ordered/numeric and so grant it via
    `ALLOWED_OPS_BY_FIELD` (0001's per-field allow-list is unchanged by this addition — it's an
    explicit allow-list, not `frozenset(ContactFieldOp)`, so a new enum member doesn't silently
    become available on existing fields).
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
  - `set_by_user_id` is recorded as the authenticated caller's `request.state.user.id`, whether
    that request came in via API key or JWT.
  - Re-creating a soft-deleted definition's `name` (after a delete-and-recreate) succeeds; a
    duplicate `name` while the original is still active is rejected (422/409).
- **Event ingestion Celery task** (tested directly, called with a plain dict the way `orcha`'s
  `process_nats_event_task` tests do — no live NATS connection needed):
  - A well-formed envelope for a known `user.id` creates a `ContactCustomEvent` row with correctly
    extracted `name`/`occurred_at`/`properties`, without modifying the existing contact's
    email/name.
  - A well-formed envelope for an unknown `user.id` upserts a new `Contact` (with the envelope's
    `user.email`/`first_name`/`last_name`) and then records the event against it.
  - A second event for an already-known `user.id` never overwrites that contact's identity fields,
    even if the envelope's `user.email` differs from what's stored (documents which one wins, since
    contacts can also be edited independently in Looply).
  - The full `raw_envelope` is stored verbatim regardless of which fields were extracted.
- **NATS subscriber wiring** (thin, following `orcha`'s `tests/app/messaging/test_nats_subscriber.py`
  style): a received message is dispatched to the ingestion Celery task via `.delay(msg)` — this
  layer has no business logic of its own to test beyond "message in, task dispatched."
- **Repository-level CRUD tests** for `CustomFieldDefinition` (create/list/soft-delete, immutable
  `value_type`), following `tests/app/repositories/test_contact_list_repository.py`'s style.
- **Router tests** for the field-value write and read/list endpoints (event ingestion has no
  router — see above), including the RBAC permission checks (`custom_data:write`/`custom_data:read`)
  and the 404 (unknown `external_id` on a field write)/422 (unknown field, type mismatch) error
  paths.

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
- **An HTTP fallback path for event ingestion** — NATS (matching `orcha`'s pattern) is the only
  ingestion transport this PRD ships. A host that can't or won't publish onto the shared
  `EVT_LINDEN` JetStream stream directly has no alternative endpoint to call. Revisit if a future
  host platform needs one.
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
- Event ingestion's NATS transport (worker process, FastStream/`NatsBroker`, JetStream
  subscription, dispatch-to-Celery-task split) is not a new design — it's `orcha`
  (`~/sites/linden-family/orcha`)'s existing pattern for consuming this exact same class of Linden
  domain events, reused here rather than reinvented. See "Custom Events" → "Ingestion transport"
  above for the concrete mapping from `orcha`'s files (`run_nats_worker.py`,
  `app/messaging/nats_subscriber.py`, `app/tasks/process_nats_event_task.py`) to Looply's
  equivalents.
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
  Looply's NATS-ingested Celery task only ever reads `event_type`, `time`, `event_data`, and `user`
  from this — `source`, `spec_version`, `subject`, `tags`, `labels`, and the envelope's own `id`
  are stored in `raw_envelope` for audit but not otherwise interpreted.
- The original motivating example — "campaign for users who haven't yet created a family
  member" — is expressible once this ships as a single `custom_event` segment condition:
  `{"type": "custom_event", "event_name": "com.mylinden.person.created", "op": "has_not"}` — no
  `custom_field` needed for that specific case, since a count isn't actually required to express
  "hasn't happened yet." Fields remain valuable for genuinely value-based conditions, which an
  event log alone can't express as cleanly — e.g. a "large family" segment:
  ```json
  {
    "type": "custom_field",
    "field_name": "family_member_count",
    "operator": ">=",
    "value": 3
  }
  ```
  using the `GTE` operator this PRD adds to the shared `ContactFieldOp` enum (see "Segment rule
  tree integration" above) specifically for `NUMBER`/`DATE` custom fields.

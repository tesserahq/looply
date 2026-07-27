# Feature: Campaigns

**ID**: `feat-001`
**Status**: Approved
**Created**: 2026-07-27

---

## Summary

A Campaign lets a Looply user send one Looply contact list to Sendly for delivery. Looply owns the campaign draft, the selected contact list, and resolving eligible recipients at send time; Sendly owns templates, rendering, suppression, and the actual broadcast delivery. Looply calls `tessera_sdk.clients.sendly.SendlyClient` to hand off the send, stores the returned batch ID, and polls Sendly asynchronously to learn when the send finishes. Full domain spec: `docs/campaign.md`.

---

## Target Users

- **Primary**: Looply users (e.g. marketers, community managers) who want to email an existing contact list once, immediately, without building their own email infrastructure.
- **Context**: Ad-hoc, one-time sends from within Looply — create a draft campaign against a contact list and a live Sendly template, then send it and watch its status move from draft → sending → completed/failed.

---

## Scope

### In Scope

- [ ] `Campaign` model: `id`, `name`, `status` (`draft`/`sending`/`completed`/`failed`), `contact_list_id`, `project_id` (nullable), `template_id` (nullable), `template_variables`, `from_email`, `subject`, `tags`, `batch_id`, `sent_at`, `completed_at`, `created_by_id`
- [ ] CRUD API: create, list, get, update (draft-only), delete
- [ ] `POST /campaigns/{id}/send`: resolves eligible recipients (active, has email, deduped by email) from the campaign's contact list, calls `SendlyClient.send_broadcast()` with `idempotency_key=f"campaign:{id}"`, persists `batch_id` and moves status to `sending`
- [ ] A Celery beat task polling all `sending` campaigns every 60s via `SendlyClient.get_broadcast()`, marking `completed` (+`completed_at`) when Sendly reports `finished: true`
- [ ] Blocking validation: non-draft status blocks send/update (400); zero eligible recipients blocks send (400) before calling Sendly
- [ ] RBAC on all campaign routes via `tessera_sdk`'s Custos-backed `authorize()`, resource `looply.campaign`, actions `create`/`read`/`update`/`delete` (send reuses `update`), domain fixed to `"*"` (no per-tenant domain concept exists in Looply yet)

### Out of Scope (this iteration)

- Scheduled/future-dated sends
- Segments, saved queries, or manual recipient selection (only "one contact list" is supported)
- Any Looply-side delivery-event table, per-recipient outcome storage, or duplicated delivery metrics — Sendly remains the source of truth, queried by `batch_id`/tags
- Authorization/ownership restrictions on campaigns (any authenticated user can view/edit/send any campaign)
- A reporting view backed by Sendly data (`docs/campaign.md` future work)

### Dependencies

- `tessera_sdk` (`clients.sendly.SendlyClient`, `infra.auth_token_provider.AuthTokenProvider`, and its own `config.get_settings().sendly_api_url`) — already an installed git dependency, confirmed importable in the current environment.
- An in-flight change to `tessera-sdk-py` making `SendBroadcastRequest.project_id` optional (owned by the user, tracked outside this repo) — this feature assumes it lands before `project_id` can safely be omitted on send.
- Celery + Redis, already configured in this repo (`app/core/celery_app.py`) but with zero active tasks prior to this feature — this is the first live task and the first `beat_schedule` entry. Deploying an actual running `celery beat` process is an operational follow-up outside this repo's code.
- Custos (via `tessera_sdk.server.dependencies.authorization.authorize`, requires `custos_api_url` configured) — this is the first use of Custos-backed RBAC anywhere in Looply; added mid-implementation after an automated security review flagged unauthenticated campaign routes.

---

## Key Decisions

| Decision | Rationale | Alternatives Considered |
|----------|-----------|-------------------------|
| `project_id` is nullable on `Campaign`, passed through to Sendly as-is | No `Project` model exists in Looply; `project_id` is a foreign reference into Sendly's domain. User is updating the SDK to accept `None`. | Validating/blocking on missing `project_id` at send time — rejected once the SDK change was confirmed in-flight |
| Send executes synchronously inside `POST /campaigns/{id}/send` | Sendly's `send_broadcast()` returns quickly (accept-only, doesn't wait for delivery); the idempotency key already makes retries safe without needing async infra | Celery task for the send itself — rejected as unnecessary given the fast, idempotent call |
| Sendly credentials via `AuthTokenProvider().get_token()` + `tessera_sdk` config's `sendly_api_url` | Matches an existing SDK-provided auth pattern (Identies OAuth client-credentials / Auth0 M2M fallback); `sendly_api_url` is already a `tessera_sdk` Settings field, avoiding new app-level config | Adding `SENDLY_*` fields to `app/config.py` — rejected once it was confirmed `tessera_sdk`'s own Settings already has `sendly_api_url` |
| Status polling via new Celery beat task (60s interval), never marks `failed` | No background poller exists in this repo yet; doc requires learning when Sendly finishes a send. Only the initial send failing should mark a campaign `failed`, so poll failures are logged and retried next tick indefinitely | A `GET /campaigns/{id}/status` on-demand endpoint — rejected in favor of beat so status updates without client action |
| CRUD scope: create/list/get/update(draft-only)/delete + send | Matches existing `ContactList` CRUD shape; a draft campaign should be editable before it's sent, but immutable once sent | Minimal create/get/list/send-only — rejected, editing a draft before sending is a reasonable v1 need |
| No ownership/authorization restriction on campaigns | Matches the explicit answer given; no existing precedent for `project_id`-based authorization in this codebase | `created_by_id`-scoped restrictions (like nothing currently enforces this codebase-wide beyond audit trail) — rejected for v1 |
| `Contact.job` maps to recipient `attributes["job_title"]` | The doc's recipient table names `job_title`, but the actual `Contact` model column is `job` — reconciled by keeping the Sendly-facing key as `job_title` | Renaming the `Contact.job` column — rejected as out of scope and unnecessarily invasive |
| Zero eligible recipients blocks send with 400 | `SendBroadcastRequest.recipients` requires `min_length=1`; a clean 400 with a clear message is better than surfacing an SDK/Pydantic validation error | Letting the SDK call fail naturally — rejected for a worse error message and a wasted network call |
| Recipient resolution and Sendly-client construction stay inline/shared-factory, not full service classes | Only one call site exists today for recipient mapping (no `app/services/` package exists elsewhere in this repo); Sendly client construction has two real call sites today (send command + poller), justifying one small shared factory | Full `CampaignRecipientResolver` service class in new `app/services/` package — rejected as premature abstraction for a single call site; revisit when segments/saved queries land |
| Recipient dedup via SQL `DISTINCT ON (email)` | Avoids loading full contact-list membership into memory for large lists; repo already targets Postgres exclusively | Python-side dedup with a set/dict — rejected as unnecessary given DISTINCT ON is straightforward here |
| RBAC via `tessera_sdk.server.dependencies.authorization.authorize`, mirroring Sendly's `app/auth/rbac.py`, with a fixed `"*"` domain | An automated security review flagged campaign routes as unauthenticated; the user asked to mirror Sendly's RBAC pattern. Looply has no existing per-tenant/domain concept (unlike Sendly's own `project_id`), so a wildcard domain authorizes by resource+action per user without inventing a domain concept prematurely | Using `Campaign.project_id` as the domain — rejected since it's nullable, optional, and Sendly's domain, not a Looply tenant boundary |
| `mark_sending`/`mark_failed` are conditional writes (`WHERE status = draft`), not unconditional updates | Code review found that two concurrent `send` requests could otherwise race: a losing request's exhausted-retry failure could overwrite a winning request's successful `sending` state back to `failed`, violating the "only mark failed from the initial send" invariant | An unconditional update with no guard — the original implementation; replaced after the race was identified |

---

## Architecture

### Chosen Approach

A middle-ground blueprint between "everything inline" and "fully layered": the standard model → constants → repository → schema → command → router stack used everywhere else in this codebase (mirroring `ContactList`/`SubscribeUserCommand` conventions exactly), plus exactly one shared seam — a `build_sendly_client()` factory — because that piece of wiring genuinely has two call sites today (the send command and the poller task). Recipient resolution (contact list → deduped, eligible `BroadcastRecipient` list) stays as a private method inline in `SendCampaignCommand` rather than a new service class, since it has only one call site today and this repo has no existing `app/services/` package to extend.

### Trade-offs

- **Pros**: Follows every existing convention in this codebase closely (fastest to review, lowest risk of drift from house style); the one new abstraction (`build_sendly_client()`) has immediate, concrete justification rather than speculative future-proofing; recipient-mapping logic is trivially extractable later if/when segments or saved queries are added.
- **Cons / Mitigations**: If audience-resolution logic grows more complex with future audience types (segments, saved queries), it will need to be extracted out of the command at that point — acceptable since it's a small, deliberate deferral, not a design flaw today. The Celery beat poller is the first live task/schedule in this repo, so it introduces new operational surface (a `celery beat` process needs to be deployed somewhere) that this repo's code alone does not cover.

### Implementation Notes

- **Key files**:
  - `app/models/campaign.py`, `app/constants/campaign.py`
  - `app/repositories/campaign_repository.py`; extend `app/repositories/contact_list_repository.py` with `get_eligible_campaign_recipients`
  - `app/schemas/campaign.py`
  - `app/integrations/sendly_client_factory.py` (new package)
  - `app/commands/campaign/send_campaign_command.py` (new package)
  - `app/auth/rbac.py` (new package; first use of Custos-backed RBAC in Looply)
  - `app/routers/campaign.py`; register in `app/main.py`
  - `app/tasks/poll_campaign_status.py`; wire into `app/core/celery_app.py` (`beat_schedule`) and `app/tasks/__init__.py`
  - `alembic/versions/..._add_campaigns.py`
  - Tests under `tests/fixtures/campaign_fixtures.py`, `tests/app/commands/`, `tests/app/repositories/`, `tests/app/routers/`, `tests/app/tasks/`
- **Extension points**: `SendCampaignCommand`'s recipient-mapping method is the seam to extract into a resolver class if segments/saved queries/manual selection are added later; `build_sendly_client()` is the seam to extend with timeout/retry/circuit-breaker config if needed by a future reporting view that queries Sendly by `batch_id`/tags.
- **Constraints**: No retry library (`tenacity`/`backoff`) is a dependency — the send command's retry-on-failure uses a small manual loop. `SendBroadcastRequest.recipients` requires at least 1 entry. Soft-delete is enforced globally via the existing `do_orm_execute` listener, so `Campaign` uses the standard `TimestampMixin`/`SoftDeleteMixin` like every other model.

---

## Open Questions

- [ ] Deploying an actual running `celery beat` process for `poll_campaign_status` is outside this repo's code and needs to be scheduled as ops follow-up.
- [ ] The `tessera-sdk-py` change making `SendBroadcastRequest.project_id` optional is in-flight (owned by the user) — this feature's `project_id`-omitted send path is written against that expected shape.

---

## Changelog

| Date | Change |
|------|--------|
| 2026-07-27 | Initial draft |

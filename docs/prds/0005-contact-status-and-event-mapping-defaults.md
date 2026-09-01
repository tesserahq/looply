## Problem Statement

Contacts have a boolean `is_active` column that gates whether a contact is treated as "active" — it filters the active-contacts listing and, more importantly, it's the switch that decides whether a contact receives campaign sends at all. In practice, nothing in the system ever sets it to `false`: every contact, created manually or auto-created from an ingested event, ends up permanently `is_active=true`. The one repository method that could flip it (`toggle_contact_active_status`) has no API route wired to it, so it's dead code.

Separately, `EventMapping` (docs/prds/0004-event-mapping-consolidation.md) already lets an operator declare how an ingested event auto-creates or resolves a `Contact`, and fills in its identity and a handful of mapped fields. It has no way to say anything about the *lifecycle* of a contact created this way (should it be immediately treated as active, or held back until someone reviews it?) or to *tag* it at creation, even though tagging and status-setting are both things an operator can already do by hand through the regular contact API.

The user (a Looply operator/developer) wants to:
1. Understand what `is_active` is actually for, since it currently has no working "off" path.
2. Control, per event source, what status and tags a contact gets when it's auto-created from an event.

## Solution

Replace the boolean `Contact.is_active` with a three-valued `Contact.status` (`active | inactive | pending`), and let `EventMapping` declare a `default_status` and a static `default_tags` list that get stamped onto a contact only at the moment it is auto-created from an event — never re-applied to a contact that already exists, so an operator's manual corrections stay safe from being overwritten by a later event of the same type.

This gives the `is_active` flag (renamed and widened to `status`) an actual producer for the first time — event ingestion — while giving operators a third state (`pending`) to express "this contact exists but shouldn't be treated as fully active yet," a distinction the current boolean can't make.

## User Stories

1. As a Looply operator configuring an EventMapping, I want to set a default status for contacts auto-created from that event type, so that leads coming from a low-trust or unverified source don't immediately count as active.
2. As a Looply operator configuring an EventMapping, I want to set a default status of `active` for a trusted event source, so that contacts from it are immediately eligible for campaign sends without a manual step.
3. As a Looply operator configuring an EventMapping, I want to assign one or more tags to contacts auto-created from that event type, so that I can segment and target them later without manually tagging each one.
4. As a marketer building a campaign segment, I want to filter contacts by `status`, so that I can target only active contacts, or build a re-engagement segment of `pending`/`inactive` contacts.
5. As a marketer building a campaign segment, I want to filter contacts using `status IN (active, pending)`, so that I can express "not explicitly inactive" without writing multiple OR conditions.
6. As a marketer sending a campaign, I want only `active` contacts to receive it, so that pending or deactivated contacts are never accidentally emailed.
7. As an operator, I want a contact I've manually corrected (including its status or tags) to never be silently overwritten by a later event for the same identity, so that automated ingestion can't clobber my corrections.
8. As an API consumer creating a contact manually, I want it to default to `status=active`, so that existing integrations that relied on `is_active=true` by default keep working without changes.
9. As a developer maintaining the codebase, I want the dead `toggle_contact_active_status` method removed rather than adapted, so that there's no unreachable code pretending to be a real capability.
10. As a developer running the migration, I want `is_active=true` contacts to backfill to `status=active` and `is_active=false` to `status=inactive`, so that no contact's effective send-eligibility changes as a side effect of the migration itself.
11. As a developer, I want a before/after parity check on which contacts are campaign-send-eligible, so that a mistake in the backfill or the filter rewrite can't silently change who gets emailed.
12. As a developer reading the `Contact` model, I want `status` (lifecycle) to be clearly distinct from `state` (the existing US mailing-address field), so that the two aren't confused in code, schemas, or segment rules.
13. As an operator, I want tags applied via an EventMapping's `default_tags` to go through the same tag-write path as manual tagging, so that tag rows stay consistent and atomic regardless of how they were created.

## Implementation Decisions

**Contact status**
- Replace the `is_active: bool` column on `Contact` with `status: str`, restricted at the application layer to `active | inactive | pending` via a `ContactStatus(str, Enum)`, following the same pattern already used for `ContactType` (plain string column + Python enum + app-level validation, no DB check constraint — kept consistent with existing precedent rather than introducing a new validation style for one field).
- Default for manually/API-created contacts: `status=active` (preserves today's `is_active=True` default behavior).
- Campaign-send eligibility changes from `Contact.is_active.is_(True)` to `Contact.status == ContactStatus.ACTIVE`. Only `active` contacts are sendable; `pending` and `inactive` are both excluded.
- The "active contacts" listing repository method is re-pointed at `status == active` instead of `is_active == True`.
- `toggle_contact_active_status` is deleted, not adapted — it has no caller today, and a three-valued field doesn't have a meaningful "toggle" anyway. Post-creation status changes go through the existing contact-update path (setting `status` like any other field), consistent with user story 8's request for an explicit promotion API remaining open (see below).

**EventMapping defaults**
- `EventMapping` gains `default_status: str | None` (validated against `ContactStatus` when set; `None` means "don't set it, fall back to the column default of `active`") and `default_tags: list[str] | None` (a static list of tag names, same shape tags already take elsewhere in the API).
- Both are applied only inside `ContactRepository.get_or_create_from_event`, only on the creation branch (never on the "existing contact found" branch), preserving the method's existing no-clobber guarantee for known identities.
- `default_tags` is applied through the existing `TagRepository.set_contact_tags` write path (get-or-create tags, then associate), the same path manual contact create/update already use — not a second, parallel way of writing `contact_tags` rows.
- The event-ingestion call site (`process_nats_event_task`) passes the resolved `EventMapping`'s `default_status`/`default_tags` through to `get_or_create_from_event` alongside the identity and field-mapping values it already passes.

**Segment rules**
- `ContactFieldName.IS_ACTIVE` is renamed to `ContactFieldName.STATUS`.
- Allowed operators widen from `{EQ, NEQ}` to `{EQ, NEQ, IN}`, since `status` has three values instead of two and "any of a set" is a genuinely useful filter (e.g. "active or pending" for a re-engagement segment) — mirroring the `IN` support other string fields already have.
- Value validation requires a string (or list of strings, for `IN`) drawn from `ContactStatus`, replacing today's boolean-only check.

**Migration**
- Single hard-cutover migration: add `status`, backfill (`is_active=true → status='active'`, `is_active=false → status='inactive'`), drop `is_active`. No dual-write transition period — chosen because `is_active` has no live external consumers today (the only mutator, `toggle_contact_active_status`, is unreachable), so there's nothing to keep in sync during a transition window.
- All in-code usage sites are updated in the same change: campaign send filter, active-contacts listing, contact create/update/read schemas, segment rule field enum and validation, and the docstring example in the filtering utility.

**Open questions (not resolved by this PRD):**
- What API surface exists for setting or promoting a contact's `status` after creation (e.g. a dedicated endpoint vs. the general contact-update endpoint accepting a `status` field). User story 8 assumes *some* path exists but this PRD doesn't design it.
- Whether `pending` needs any automatic promotion mechanism (a follow-up event, a review queue/UI) or stays a purely manual, operator-driven transition for now. Assumed manual-only until a real need for automation shows up.

## Testing Decisions

Good tests here exercise observable behavior — what a repository call returns or what a filter query matches — not internal SQL or column names, consistent with how existing repository/schema tests in this codebase are written (e.g. the event-mapping and segment-rule test suites from 0003/0004).

- `ContactRepository.get_or_create_from_event`: verify a new contact created via an `EventMapping` with `default_status`/`default_tags` set gets that status and those tags; verify an *existing* contact matched by identity keeps its current status/tags untouched even when the mapping's defaults differ (the no-clobber guarantee — this is the highest-value test in this PRD, since it's the one invariant most likely to silently regress).
- `CampaignRepository`'s recipient-resolution query: parity test asserting the same set of contacts is send-eligible before and after the migration, using a fixture with a mix of previously `is_active=true/false` contacts. This directly covers the PRD's called-out risk.
- Segment rule validation (`ContactFieldCondition`): valid/invalid `status` values, `IN` with a list, and rejection of the old boolean-shaped input.
- Migration backfill: a data-migration test (or a query run against a seeded pre-migration state) confirming `is_active=true → active` and `is_active=false → inactive` for every row, with no unmapped values.

Not tested at the unit level: the exact wiring between `process_nats_event_task` and `get_or_create_from_event` beyond what 0003/0004's existing ingestion tests already cover — this PRD only adds two new pass-through arguments to an already-tested path.

## Out of Scope

- Any API endpoint for manually promoting/demoting a contact's `status` post-creation (open question above).
- Automatic promotion of `pending` contacts (open question above).
- Dynamic/payload-derived tags or status on `EventMapping` (e.g. extracting a tag value from the event body) — `default_tags`/`default_status` are static, mapping-level configuration only.
- Re-applying `default_status`/`default_tags` to a contact on any event after its first creation.
- Any change to `Contact.state` (the mailing-address field) or its segment-rule usage — explicitly untouched, called out here only to rule out confusion with the new `status` field.
- Bulk contact creation (`bulk_create_contacts`) picking up `default_tags`/`default_status` semantics — it's a separate manual-import path, not part of event ingestion.

## Further Notes

The naming collision between the new `status` (lifecycle) and the existing `state` (US mailing-address abbreviation) was a real point of confusion during design and is worth calling out explicitly in code review of the implementing PR — a reviewer skimming a diff that touches both `Contact.state` and `Contact.status` should not assume they're related.

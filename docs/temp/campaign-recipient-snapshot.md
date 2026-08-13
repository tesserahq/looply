# Design note: Campaign recipient snapshot

## Problem

A campaign's audience is `contact_list_id`, resolved live against `contact_list_members` at send
time (`ContactListRepository.get_eligible_campaign_recipients`). Because list membership can
change after a campaign is sent (contacts added/removed from the list, deactivated, or deleted),
there is no durable record of who a given campaign was actually sent to. Looking at a completed
campaign today only tells you the *current* membership of its list, not the audience at send time.

## Decision

Add a new join table, `CampaignRecipient`, that snapshots the resolved audience once a campaign's
broadcast is accepted by Sendly.

### Schema

`campaign_recipients`

| Field | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `campaign_id` | UUID FK → `campaigns.id` | |
| `contact_id` | UUID FK → `contacts.id` | Live reference, not a data snapshot |
| `created_at` / `updated_at` | timestamps | via `TimestampMixin` |

Unique constraint on `(campaign_id, contact_id)`.

No `email`/`first_name`/`last_name` snapshot columns, and no `status` column. See "Explicitly out
of scope" below.

### Where it's written

In `SendCampaignCommand.execute` (`app/commands/campaign/send_campaign_command.py`), immediately
after `SendlyClient.send_broadcast()` succeeds and alongside `CampaignRepository.mark_sending`:
resolve recipients (same list already computed for the Sendly call), insert one
`CampaignRecipient` row per contact.

- If the Sendly call fails, no rows are written — `mark_failed` leaves no snapshot, consistent
  with "one send per campaign, ever" (see below).
- The recipient-resolution query used for the Sendly payload and the one used for the snapshot
  must stay the same query, so the snapshot always matches what Sendly actually received.

**Open follow-up:** the recipient-row insert and `mark_sending` are two separate writes right
after the Sendly call succeeds. If the process crashes between them, a campaign could end up
`sending`/`completed` with no recipient snapshot. These two writes should happen in the same DB
transaction.

### Why contact_id only, not a data snapshot

Chosen deliberately over snapshotting `email`/`name` at send time: keeps the table minimal, and
"who did we send to" is answered by an existing `Contact` reference. This does mean that if a
contact's email is changed or the contact is deleted after a campaign was sent, the recipient
row's contact-level details will reflect the *current* contact state, not what Sendly actually
received at the time. Historical accuracy of contact details is not a goal of this table — Sendly
remains the source of truth for what was actually delivered to which address (per
`docs/campaign.md`'s existing division of responsibility).

### No resend / uniqueness

Campaign status is `draft → sending → completed/failed` with no resend path today. A `failed`
campaign is not retried in place; a new campaign is created. So `(campaign_id, contact_id)` can be
enforced unique with no need for an attempt/generation column.

### Explicitly out of scope (this change)

- Per-recipient delivery status (sent/delivered/opened/clicked/bounced). This table only records
  *who was in scope for the send*, not delivery outcomes. Delivery-level facts still come from
  Sendly via `batch_id`, per `docs/campaign.md`. A follow-up GitHub issue tracks adding a `status`
  column (or a separate events table) once that Sendly integration is scoped.
- Any change to how recipients are resolved (still `get_eligible_campaign_recipients`: active,
  has email, deduped by email).
- Support for resending a campaign.

## Doc updates needed

`docs/campaign.md` should note that Looply now persists the resolved recipient list (contact IDs
only) at send time, and clarify that this is an audience snapshot, not a delivery-event table —
delivery outcomes are still exclusively Sendly's concern.

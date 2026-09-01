# 0006 — Campaign Analytics Report

## Goal

Give users a per-campaign report showing how a sent campaign performed —
standard email metrics plus a couple of charts — using data Looply already
tracks. No cross-campaign dashboard, no new Sendly work, in this phase.

## Scope: v1 (buildable now, no Sendly changes needed)

### Metrics

Computed server-side (not left to the frontend to divide) and returned
alongside the existing campaign response:

| Metric | Formula | Source |
|---|---|---|
| Delivery rate | `delivered_count / recipient_count` | `Campaign` aggregate |
| Bounce rate | `bounced_count / recipient_count` | `Campaign` aggregate |
| Open rate | `opened_count / delivered_count` | `Campaign` aggregate |
| Click rate | `clicked_count / delivered_count` | `Campaign` aggregate |
| Click-to-open rate (CTOR) | `clicked_count / opened_count` | `Campaign` aggregate |
| Complaint rate | `complained_count / delivered_count` | `Campaign` aggregate |

All six use fields that already exist on `Campaign` — no new sync work.
Open/click/CTOR are computed against `delivered_count`, not total
recipients, matching Mailchimp/Loops convention (a bounced email never had
a chance to be opened).

Complaint rate was initially cut for v1 as "low value," but since
`complained_count` is already synced from Sendly's `get_broadcast()`, it's
zero-cost to include and is the metric most predictive of ISP-level sender
reputation problems.

**Not included**: unsubscribe rate. See "Requirements from Sendly" below —
attributing an unsubscribe to a specific campaign isn't possible with data
Looply currently has access to.

### Charts

Two charts, both computable from data already stored, no schema changes:

1. **Funnel/bar chart** — Recipients → Delivered → Opened → Clicked, from
   the same `Campaign` aggregate counts as the metrics above.
2. **Engagement-over-time histogram** — opens/clicks bucketed by time
   elapsed since `Campaign.sent_at`, using the per-recipient
   `CampaignRecipient.opened_at` / `clicked_at` timestamps (first
   occurrence only — this is what's currently stored, no per-event log
   exists). Needs a new bucketing query; bucket intervals (hour/day/week)
   TBD at implementation time.

### Surface

- New/extended API response exposing the six computed rate fields (exact
  endpoint shape — new `GET /campaigns/{id}/stats` vs. extending the
  existing campaign response — TBD at implementation time).
- UI: a report view on the existing campaign detail page
  (`looply-portal`'s `app/routes/main/campaigns/detail/overview.tsx`),
  using **recharts** for the charts. `looply-portal` has no charting
  library or existing chart pattern today; recharts matches
  `modela-portal`'s existing choice and shadcn/ui's standard pairing, so
  this introduces no new tooling decision across the two portals.

### Explicitly out of scope for v1

- Cross-campaign trends/dashboard (needs a rollup layer that doesn't
  exist yet — deferred to a later phase, not blocked on Sendly).
- Per-link click map (needs per-link click data — see below, unconfirmed
  whether Sendly exposes this).
- Unsubscribe rate (see below).

## Requirements from Sendly (blocking future phases, not v1)

Investigation into Sendly's existing webhook/suppression handling found:

- Postmark webhooks for `Bounce` and `SpamComplaint` are parsed and
  written as terminal statuses on the `Email` row
  (`app/providers/postmark_provider.py:140-143`,
  `EmailLifecycleService`).
- `SubscriptionChange` (unsubscribe/resubscribe) events are parsed and
  written to an `EmailSuppression` table (project-scoped: email +
  `unsubscribed_at` + source) via `HandleSubscriptionChangeCommand`, which
  also publishes an `email.unsubscribed` NATS event.
- Only `SendBroadcastCommand` checks `EmailSuppression` before sending
  (`is_suppressed_bulk` / `is_suppressed_bulk_any_project`) — suppressed
  recipients are skipped on broadcast sends.

**Gap 1 — unsubscribe attribution** ([sendly#113](https://github.com/tesserahq/sendly/issues/113)). `EmailSuppression` has no
`campaign_id` (or any link back to the broadcast/send that produced the
unsubscribe). To show an unsubscribe rate on a specific campaign's report,
Sendly needs to either:
  - capture which campaign/broadcast the unsubscribe link belonged to at
    webhook-ingestion time and store it on the suppression row, or
  - expose enough data (e.g. broadcast ID on the unsubscribe link/webhook
    payload) for Looply to do the attribution itself.

A time-window heuristic (match `unsubscribed_at` falling shortly after a
campaign's `sent_at` for a recipient on that campaign) was considered as a
Looply-side workaround but rejected as too approximate to ship — filed
here as a Sendly requirement instead of a Looply guess.

**Gap 2 — bounces/complaints don't suppress future sends** ([sendly#114](https://github.com/tesserahq/sendly/issues/114)). Only
`SubscriptionChange` (unsubscribe) writes to `EmailSuppression`. A hard
bounce or spam complaint changes `Email.status` but does **not** add the
address to the suppression table — nothing stops that address from being
emailed again on the next broadcast or single send. This is a
deliverability risk independent of the analytics feature and worth its
own issue with Sendly, not just a documentation note here.

**Gap 3 — per-link click data (for a future click map)** ([sendly#115](https://github.com/tesserahq/sendly/issues/115)). Unconfirmed
whether Sendly's broadcast API exposes which specific link was clicked,
or only that *a* click happened. Needs a spike before a click-map feature
can be scoped.

## Open items

- Exact API endpoint shape (new endpoint vs. extending existing response).
- Histogram bucket intervals for the engagement-over-time chart.
- Gaps 1–3 filed as separate Sendly issues: [#113](https://github.com/tesserahq/sendly/issues/113), [#114](https://github.com/tesserahq/sendly/issues/114), [#115](https://github.com/tesserahq/sendly/issues/115).

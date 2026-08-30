# Campaigns

A campaign lets Looply email one contact list. Looply chooses the audience and asks Sendly to deliver it.

## Scope

The first version supports an immediate, one-time send to one Looply contact list. Scheduled sends, segments, saved queries, and manual recipient selection are future work.

## Responsibilities

| Looply owns | Sendly owns |
| --- | --- |
| Campaign draft and status | Templates and layouts |
| The selected contact list | Rendering and personalization |
| Resolving eligible contacts at send time | Suppression and unsubscribe checks |
| Calling Sendly through `tessera-sdk` | Broadcast queueing and delivery |
| The returned Sendly batch ID | Per-recipient delivery records and events |
| A bounded-window cache of first-open/first-click timestamps and result counts | Sendly's full delivery-event history |

Looply must not create its own email HTML or delivery jobs, and must not duplicate Sendly's full
delivery-event history. The one deliberate, scoped exception is the narrow engagement cache
described in "Engagement cache" below: first-occurrence `opened_at`/`clicked_at` timestamps and
campaign-level result counts, refreshed for a bounded window after a campaign completes. Sendly
remains the source of truth for everything beyond that — per-event history, multiple
opens/clicks, bounces, complaints, and anything after the polling window closes.

## Campaign data

| Field | Description |
| --- | --- |
| `id` | Looply campaign ID |
| `name` | Internal name |
| `status` | `draft`, `sending`, `completed`, or `failed` |
| `contact_list_id` | The one Looply contact list to send to |
| `project_id` | Project that owns the template and broadcast |
| `template_id` | A live template reference |
| `template_variables` | Shared variables for the template |
| `from_email` | Optional sender override; Sendly uses the template default when omitted |
| `subject` | Optional subject override; Sendly uses the template subject when omitted |
| `tags` | Optional campaign tags forwarded to Sendly |
| `batch_id` | Batch ID returned after the broadcast is accepted |
| `sent_at` | When Sendly accepted the broadcast |
| `completed_at` | When Sendly reports the send stage finished |
| `delivered_count`, `bounced_count`, `complained_count`, `opened_count`, `clicked_count` | Result counts, refreshed from Sendly while inside the engagement polling window |
| `engagement_last_synced_at` | When engagement data was last *fully* refreshed from Sendly; `None` if no successful refresh has happened yet |
| `engagement_polling_expires_at` | When Looply stops refreshing this campaign's engagement data (`completed_at` + the global polling window) |

The template belongs to Sendly and remains live until the campaign is sent. Its layout is therefore also a Sendly concern; Looply stores neither a layout ID nor email HTML.

## Send a campaign

When a user sends a draft campaign, Looply:

1. Loads the campaign's contact list.
2. Keeps active contacts with an email address and deduplicates by email.
3. Converts each contact into a Sendly broadcast recipient.
4. Calls `SendlyClient.send_broadcast()` with the campaign's live template, variables, tags, and recipients.
5. Stores the returned `batch_id`, changes the campaign to `sending`, and records the resolved contacts as `CampaignRecipient` rows (`campaign_id`, `contact_id`) — a snapshot of who the campaign was sent to, since contact list membership can change afterward.

Sendly then renders and sends asynchronously. It automatically excludes suppressed recipients.

```text
Looply campaign + contact list
          |
          v
Resolve active, unique email recipients
          |
          v
tessera-sdk: SendlyClient.send_broadcast()
          |
          v
Sendly template/layout + suppression + broadcast delivery
```

### Recipient mapping

Looply passes the following contact data to Sendly:

| Looply contact field | Sendly recipient field |
| --- | --- |
| `email` | `email` |
| `first_name` | `first_name` |
| `last_name` | `last_name` |
| `company`, `job_title`, `contact_type` | `attributes` |

Sendly merges each recipient's fields and `attributes` with the campaign's `template_variables` when rendering the template.

### SDK call

```python
from tessera_sdk.clients.sendly import (
    BroadcastRecipient,
    SendBroadcastRequest,
    SendlyClient,
)

request = SendBroadcastRequest(
    project_id=campaign.project_id,
    template_id=campaign.template_id,
    template_variables=campaign.template_variables,
    from_email=campaign.from_email,
    subject=campaign.subject,
    tags=campaign.tags,
    # Retrying the same campaign must never create a second broadcast.
    idempotency_key=f"campaign:{campaign.id}",
    recipients=[
        BroadcastRecipient(
            email=contact.email,
            first_name=contact.first_name,
            last_name=contact.last_name,
            attributes={
                "company": contact.company,
                "job_title": contact.job_title,
                "contact_type": contact.contact_type,
            },
            # Lets later engagement polling match Sendly's results back to
            # this contact without relying on the mutable email address.
            client_reference_id=contact.id,
        )
        for contact in recipients
    ],
)

result = SendlyClient().send_broadcast(request)
# Persist result.batch_id on the campaign.
```

Tags are free-form labels stored on Sendly's broadcast emails. Use them to group or filter related campaigns, for example `newsletter`, `product-launch`, or `q3-2026`.

## Status and results

`send_broadcast()` returns after Sendly accepts the broadcast; it does not wait for delivery. Looply stores `batch_id` and uses `SendlyClient.get_broadcast()` to check progress.

- Mark the campaign `completed` when Sendly returns `finished: true`.
- Mark it `failed` only when Looply cannot get the broadcast accepted or retrieve it after retrying.
- Display Sendly's `queued_count`, `suppressed_count`, and `prepared_count` as progress information; do not copy them into Looply delivery records.

For recipient-level outcomes or later reporting, query Sendly by `batch_id` (or campaign tags). Sendly remains the authoritative record for sent, delivered, opened, clicked, bounced, complained, and unsubscribed emails.

## Recipient snapshot

`CampaignRecipient` records which contacts a campaign was actually sent to, since the
`contact_list_id` it points to can gain or lose members afterward. It stores
`campaign_id`, `contact_id` — a live reference, not a copy of the contact's email/name at
send time — and is written once, in the same transaction as the `sending` status update, right
after Sendly accepts the broadcast. It also carries the engagement cache described below.

## Engagement cache

Looply caches a narrow, first-occurrence slice of Sendly's engagement data so a campaign's
results can be shown inside Looply without a live call to Sendly. This is a deliberate, scoped
exception to "Looply must not duplicate Sendly's delivery-event history" above — see "Scope"
for exactly what is and isn't covered.

- **What's cached**: `CampaignRecipient.opened_at`/`clicked_at` (first-occurrence only, not a
  per-event log) and `Campaign.delivered_count`/`bounced_count`/`complained_count`/
  `opened_count`/`clicked_count`.
- **How it's refreshed**: `poll_campaign_engagement`, a Celery beat task, runs for every
  `completed` campaign still inside its polling window. For each one, it walks every page of
  `SendlyClient.iter_broadcast_recipients(batch_id=...)`, matches each result back to a
  `CampaignRecipient` by `contact_id` (sent to Sendly as `client_reference_id` — never by email,
  since email is mutable), and fills in `opened_at`/`clicked_at`. It also calls
  `get_broadcast()` to refresh the campaign's result counts. A failed lookup for one campaign is
  logged and skipped — matching `poll_campaign_status` — so it never stops the rest of the batch,
  and never advances that campaign's `engagement_last_synced_at`.
- **Bounded window**: `engagement_polling_expires_at` is fixed at `completed_at` plus a global
  default (`Settings.engagement_polling_window_days`, default 3 days) the moment a campaign is
  marked `completed`. Once passed, that campaign is never polled again — a contact who opens on
  day 5 of a 3-day window still shows as a non-opener in Looply indefinitely. There's no
  per-campaign override.
- **Freshness**: `engagement_last_synced_at` only advances after a fully successful poll pass for
  that campaign, so it's a trustworthy "data as of" timestamp even though per-item polling
  failures are swallowed — build any "data as of" UI off this field, not `completed_at` or
  `engagement_polling_expires_at`.
- **Not covered**: multiple opens/clicks per recipient, timestamps for bounces/complaints, or any
  Sendly delivery-event data beyond the fields above. For that, query Sendly directly.

## Safe retries

Every attempt to send a campaign uses the same idempotency key: `campaign:{campaign_id}`. If the first request succeeds but Looply loses the response, retrying the identical request returns the existing Sendly batch instead of sending another broadcast. Once Sendly has accepted a campaign, its content and audience must not change; create a new campaign for a different send.

## Future work

- Scheduling in Looply: persist a future time and call the same Sendly broadcast flow when it is due.
- Additional audience types: segments, saved queries, and manual selections.
- A Looply reporting view backed by Sendly data, without duplicating Sendly's delivery pipeline.

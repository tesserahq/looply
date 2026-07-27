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

Looply must not create its own email HTML, delivery jobs, delivery-event table, or duplicate delivery metrics. Sendly is the source of truth for those concerns.

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

The template belongs to Sendly and remains live until the campaign is sent. Its layout is therefore also a Sendly concern; Looply stores neither a layout ID nor email HTML.

## Send a campaign

When a user sends a draft campaign, Looply:

1. Loads the campaign's contact list.
2. Keeps active contacts with an email address and deduplicates by email.
3. Converts each contact into a Sendly broadcast recipient.
4. Calls `SendlyClient.send_broadcast()` with the campaign's live template, variables, tags, and recipients.
5. Stores the returned `batch_id` and changes the campaign to `sending`.

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

## Safe retries

Every attempt to send a campaign uses the same idempotency key: `campaign:{campaign_id}`. If the first request succeeds but Looply loses the response, retrying the identical request returns the existing Sendly batch instead of sending another broadcast. Once Sendly has accepted a campaign, its content and audience must not change; create a new campaign for a different send.

## Future work

- Scheduling in Looply: persist a future time and call the same Sendly broadcast flow when it is due.
- Additional audience types: segments, saved queries, and manual selections.
- A Looply reporting view backed by Sendly data, without duplicating Sendly's delivery pipeline.

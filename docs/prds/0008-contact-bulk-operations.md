## Problem Statement

Operators manage contacts one at a time. To deactivate 200 contacts after a list cleanup, to set the company and website for a team that works at the same place, or to tag a segment of imported leads, they have to call `PUT /contacts/{id}` once per contact. The UI has no way to select several contacts and act on them together, so every bulk task is either tedious or done by hand against the API.

Looply already has the building blocks: `Contact.status` (`active | inactive | pending`, from docs/prds/0005-contact-status-and-event-mapping-defaults.md), the full set of contact attributes on `ContactUpdate`, many-to-many tags via `TagRepository`, and soft delete with a per-contact deleted event. The waiting-list module already exposes a bulk status endpoint (`POST /waiting-lists/{id}/members/bulk-status`), so there's a precedent for the response shape.

## Solution

Add two bulk endpoints under `/contacts`:

- **`POST /contacts/bulk-update`** is the single endpoint for every attribute change. It takes a list of contact IDs, a `changes` object with any updatable contact attributes (status, contact type, company, website, address, notes, and so on), and an optional `add_tags` list. Adding a new attribute to bulk updates is a one-line change to the request schema, not a new endpoint.
- **`POST /contacts/bulk-delete`** stays separate, because deletion is destructive, needs the `delete` permission, and publishes its own events.

Each request takes an explicit list of contact IDs (at most 500) chosen from the visible page in the UI. Each runs per contact, reports how many were applied, and lists every skipped ID with a reason. A bad request fails as a whole. A request with valid input never fails because some of its contacts can't be processed.

The bulk endpoints are additive to the existing single-contact API. `PUT /contacts/{id}` and `DELETE /contacts/{id}` are unchanged.

## User Stories

1. As an operator, I want to select contacts on a page and set their status to `inactive` in one action, so that I can stop campaign sends to a group without editing each contact.
2. As an operator, I want to change a status and add a tag to the same selection in one action, so that a single cleanup doesn't take two passes.
3. As an operator, I want to set the company, website, or contact type for a group of contacts who work at the same place, so that I can update them together.
4. As an operator, I want to clear a shared field (for example, remove a company name) for the selected contacts, so that bulk edits can undo mistakes too.
5. As an operator, I want bulk tagging to keep each contact's existing tags, so that a bulk action can't silently remove tags I set earlier.
6. As an operator, I want to soft delete the selected contacts, so that I can clear out duplicates or stale records in one action.
7. As an operator, I want to know which selected contacts were not processed and why, so that I can fix them and retry.
8. As an operator, I want a request that's too large or malformed to be rejected with a clear error, so that I don't get a partial result by accident.
9. As an API consumer, I want every bulk response to use the same shape (`requested_count`, `updated_count`, `skipped`), so that I can handle all bulk operations with one piece of code.
10. As a developer adding a new updatable attribute, I want to add it to the bulk request schema and nothing else, so that bulk updates don't need a new endpoint each time.
11. As a developer, I want bulk updates to reuse the single-contact write path (`UpdateContactCommand`'s checks, `ContactRepository.update_contact`, and the `contact.updated` event), so that bulk and single edits behave identically per contact.
12. As an operator, I want a bulk delete to publish the same contact-deleted event per contact as a single delete, so that downstream consumers keep working without changes.

## Implementation Decisions

**Routes**

All three endpoints are `POST` under `/contacts`, following the `/contacts/batch` precedent. They don't use `DELETE` or `PUT` with a body, because some proxies and clients drop bodies on those methods. Each reports counts, so each returns `200`, not `204`.

| Method | Path | Operation | Permission |
|---|---|---|---|
| POST | `/contacts/bulk-update` | Change any updatable attributes and/or add tags | `rbac["update"]` |
| POST | `/contacts/bulk-delete` | Soft delete each contact | `rbac["delete"]` |

**Request shape: `bulk-update`**

- `contact_ids`: list of UUIDs. Required, at least 1, at most 500. Duplicate IDs are removed before processing and don't count twice.
- `changes`: object of attribute values to set on every selected contact. Optional. Only the fields the caller sends are changed. An explicit `null` clears a nullable field. Fields that can't be null (`contact_type`, `phone_type`, `status`) reject `null` with `422`.
- `add_tags`: list of non-empty strings, optional, at most 20 after trimming and de-duplication. Adds tags to each contact and never removes existing ones. Missing tags are created the same way `TagRepository.get_or_create_tags` creates them today.
- At least one of `changes` or `add_tags` must be present and non-empty. Otherwise the request fails with `422`.

**Which attributes can be bulk-updated**

The bulk `changes` schema is its own Pydantic model, not a reuse of `ContactUpdate`. It lists every field a bulk update may set explicitly, and it rejects any other key with `422` (`extra="forbid"`). New attributes are opted in by adding them to this model.

Allowed in v1:
`status`, `contact_type`, `company`, `job`, `website`, `address_line_1`, `address_line_2`, `city`, `state`, `zip_code`, `country`, `notes`.

Excluded, and why:
- `email`, `phone`, `external_id`: each has a uniqueness rule (`uq_contacts_email`, the `external_id` partial unique index, and the phone check in `UpdateContactCommand`). A bulk update would give several contacts the same value and fail for all but one.
- `tags` on `ContactUpdate`: that field is a full replacement of the tag set. A bulk update must never replace tags, so tags are only available through `add_tags`.
- `source`: provenance, set when a contact is created. Bulk edits shouldn't rewrite it.
- `first_name`, `middle_name`, `last_name`: left out in v1. A shared value across many people is rarely what an operator wants. Easy to add later if needed.

**Response shape**

Both endpoints return:

- `requested_count`: number of unique IDs in the request.
- `updated_count`: number of contacts the operation was applied to. A contact that already had the requested values counts as updated, so the operation is idempotent and retrying is safe.
- `skipped`: list of `{contact_id, reason}`, one entry per ID that wasn't processed.

Skip reasons:
- `not_found`: no contact with this ID, or the contact is soft deleted (the global soft-delete filter treats both the same way).

Only `not_found` is defined today. The reasons list is open so new ones can be added without a breaking change.

**Partial semantics**

- A request with valid input returns `200`, even when every ID is skipped. In that case `updated_count` is `0`. This matches the partial-success choice in the design interview.
- Validation errors fail the whole request with `422` before any work starts: an empty or oversized `contact_ids`, an unknown key in `changes`, a `null` in a non-nullable field, an invalid enum value, an empty `changes` and `add_tags` together, or an empty or oversized `add_tags`.
- Attribute values are the same for every contact in the request, so value validation happens once up front. The only per-contact failure is `not_found`.

**Write paths**

- `bulk-update` applies the `changes` values and the `add_tags` tags to each contact in one transaction per request. It uses `ContactRepository.update_contact` with `exclude_unset`, so only the fields the caller sent are written. It doesn't go through `TagRepository.set_contact_tags`, which replaces the full tag set; tags are added with a new method that inserts only missing `ContactTag` rows, relying on the `uq_contact_tags_contact_tag` unique constraint so repeated adds are safe.
- Each updated contact publishes its `contact.updated` event after commit, the same as `UpdateContactCommand`. An event per contact means a 500-contact update publishes 500 events. The publish is dispatched through `on_commit`, so it's dropped if the transaction rolls back.
- `bulk-delete` loops over the IDs through `DeleteContactCommand`, so each contact is soft deleted and gets its `contact.deleted` event, exactly as a single delete does.

**Event fan-out**

Bulk update and bulk delete each publish one event per contact. A 500-contact request publishes 500 events. This was accepted in the design interview. Before either endpoint ships, the publish loop needs a throughput check against the NATS consumers (see Testing).

**Out of scope**

- "Select all matching the current filter" (server-side resolution of a search or filter). Left for a later version.
- Bulk tag removal. Tag removal needs its own UI and confirmation.
- Bulk changes to the unique identity fields (`email`, `phone`, `external_id`) and to `source`.
- Bulk changes to contact lists or campaigns.
- Undo.

## API Examples

### Bulk update: company and website for coworkers

Request:

```http
POST /contacts/bulk-update
Content-Type: application/json

{
  "contact_ids": [
    "3f1c2a9e-7b4d-4e8a-9c21-5d6f0a1b2c3d",
    "8a2b7c10-4e5f-4a6b-8d9e-0f1a2b3c4d5e"
  ],
  "changes": {
    "company": "Acme Corp",
    "website": "https://acme.example"
  }
}
```

Response, `200 OK`:

```json
{
  "requested_count": 2,
  "updated_count": 2,
  "skipped": []
}
```

### Bulk update: status, contact type, and a tag in one request

Request:

```http
POST /contacts/bulk-update
Content-Type: application/json

{
  "contact_ids": [
    "3f1c2a9e-7b4d-4e8a-9c21-5d6f0a1b2c3d",
    "8a2b7c10-4e5f-4a6b-8d9e-0f1a2b3c4d5e",
    "c4d5e6f7-1a2b-4c3d-9e8f-7a6b5c4d3e2f"
  ],
  "changes": {
    "status": "inactive",
    "contact_type": "customer"
  },
  "add_tags": ["churned"]
}
```

Response, `200 OK`. The third ID doesn't exist (or was soft deleted):

```json
{
  "requested_count": 3,
  "updated_count": 2,
  "skipped": [
    {
      "contact_id": "c4d5e6f7-1a2b-4c3d-9e8f-7a6b5c4d3e2f",
      "reason": "not_found"
    }
  ]
}
```

### Bulk update: clearing a field

`null` clears a nullable field. Omitted fields are left alone.

Request:

```json
{
  "contact_ids": ["3f1c2a9e-7b4d-4e8a-9c21-5d6f0a1b2c3d"],
  "changes": {
    "company": null
  }
}
```

Response, `200 OK`:

```json
{
  "requested_count": 1,
  "updated_count": 1,
  "skipped": []
}
```

### Bulk update: every ID skipped

Response, `200 OK`. `updated_count` is `0`:

```json
{
  "requested_count": 2,
  "updated_count": 0,
  "skipped": [
    { "contact_id": "3f1c2a9e-7b4d-4e8a-9c21-5d6f0a1b2c3d", "reason": "not_found" },
    { "contact_id": "8a2b7c10-4e5f-4a6b-8d9e-0f1a2b3c4d5e", "reason": "not_found" }
  ]
}
```

### Bulk delete

Request:

```http
POST /contacts/bulk-delete
Content-Type: application/json

{
  "contact_ids": [
    "3f1c2a9e-7b4d-4e8a-9c21-5d6f0a1b2c3d",
    "8a2b7c10-4e5f-4a6b-8d9e-0f1a2b3c4d5e"
  ]
}
```

Response, `200 OK`:

```json
{
  "requested_count": 2,
  "updated_count": 2,
  "skipped": []
}
```

Each deleted contact publishes its `contact.deleted` event, the same as `DELETE /contacts/{id}`.

### Validation errors (`422`)

Email in `changes` (not bulk-updatable):

```json
{
  "detail": [
    {
      "type": "extra_forbidden",
      "loc": ["body", "changes", "email"],
      "msg": "Extra inputs are not permitted",
      "input": "new@example.com"
    }
  ]
}
```

Clearing a non-nullable field (`contact_type` set to `null`):

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "changes", "contact_type"],
      "msg": "Value error, cannot be cleared",
      "input": null
    }
  ]
}
```

Neither `changes` nor `add_tags` present:

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body"],
      "msg": "Value error, provide at least one of 'changes' or 'add_tags'",
      "input": { "contact_ids": ["3f1c2a9e-7b4d-4e8a-9c21-5d6f0a1b2c3d"] }
    }
  ]
}
```

Over the ID limit (501 IDs):

```json
{
  "detail": [
    {
      "type": "too_long",
      "loc": ["body", "contact_ids"],
      "msg": "List should have at most 500 items after validation, not 501",
      "input": ["..."]
    }
  ]
}
```

The `422` bodies are FastAPI's default. The rules sit on the Pydantic request schemas, so the error text comes from those rules rather than from custom handling.

## Testing Decisions

- Test the behavior of each endpoint through the router, not the implementation details of its repository calls. Each test covers one request and checks the response body and the resulting database state.
- `bulk-update`:
  - all IDs found: `updated_count == requested_count`, `skipped == []`
  - a mix of found and unknown IDs: the unknown ones show up in `skipped` with `not_found`
  - a soft-deleted contact: treated as `not_found`
  - duplicate IDs in one request: counted once
  - only the sent fields change: a `changes` request that sets `company` leaves `website` and tags untouched
  - `null` clears a nullable field; `null` on `contact_type`, `phone_type`, or `status` returns `422`
  - `email`, `phone`, `external_id`, `tags`, and `source` in `changes` return `422`
  - `add_tags` keeps each contact's existing tags
  - `changes` and `add_tags` together: both apply in one request
  - neither `changes` nor `add_tags`: `422`
  - one `contact.updated` event per updated contact, dispatched after commit
- `bulk-delete`:
  - the same skip and idempotency cases as above
  - one `contact.deleted` event per deleted contact, with the same payload as the single-delete path
- Both endpoints:
  - idempotency: running the same request twice gives the same counts and the same final state
  - `422` for an empty or oversized `contact_ids` and an empty or oversized `add_tags`
  - `403` without the `update` or `delete` permission
- Run pytest with `ENV=test` set, per the repo's testing rules, so the tests run against `looply_test`.
- Before either endpoint ships: a load check at 500 IDs against the NATS consumer, to confirm the publish loop finishes in an acceptable time and the consumers keep up.

## Open Questions

- Whether `first_name`, `middle_name`, and `last_name` should be bulk-updatable. Excluded in v1, since a shared name across many people is rarely intended.
- Whether `skipped` should carry a human-readable `message` in addition to the machine-readable `reason`. Leaning no for v1, since the UI maps reasons to text itself.
- Whether the 20-tag cap on `add_tags` is right, or whether it should match a single-contact limit, if one exists.
- Whether `status` should be carried in `changes` alongside the other attributes, or stay a top-level field like `add_tags`. Leaning `changes`, so every attribute change lives in one place.

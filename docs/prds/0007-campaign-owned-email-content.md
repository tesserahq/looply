# 0007 — Campaign-Owned Email Content

Spans four repos: **sendly**, **tessera-sdk-py**, **looply**, **looply-portal**.

## Problem Statement

A Looply campaign doesn't store its own email content. It only holds a
`template_id` that points at a Sendly template. To make that work, the portal
creates a Sendly template for every campaign:

- "Start from scratch" creates an empty Sendly template as soon as the user
  clicks it, before the campaign is saved. If the user abandons the form, the
  template stays behind.
- "Use existing template" clones a Sendly template on save, so every campaign
  gets its own copy.
- Deleting a campaign never deletes its template.

People create and delete many campaigns, so Sendly's template list fills up
with throwaway, unnamed, campaign-specific templates. That makes it hard to
find the templates that were created on purpose. Hiding these templates
behind a "private" flag would only make the clutter invisible: the templates
would still pile up, and nobody could audit or clean them.

The obvious alternative is to store the content in Looply. Done naively,
that copies the layout's HTML into every campaign, and a fix to a layout
would never reach those campaigns.

## Solution

Looply campaigns own their email **body**, and Sendly keeps owning
**layouts**. A campaign stores its subject, HTML body and a reference to a
Sendly layout. When the campaign is sent, Looply passes the body and the
layout reference inline to Sendly's broadcast endpoint, and Sendly wraps the
body in the layout. No Sendly template is created or used.

From the user's perspective:

- A new campaign starts one of two ways: **clean**, where they pick a layout
  and start with an empty body, or **duplicate an existing campaign**. Sendly
  templates are no longer offered as a starting point in Looply.
- While editing, they can preview the email exactly as it will be sent: the
  body inside the layout, with variables filled in.
- While a campaign is a draft, it uses the current version of its layout.
  When Sendly accepts the send, it saves a copy of the layout, so every
  recipient gets the same version and the sent email can be reproduced later.
- Sendly's template list contains only templates people created on purpose.
  A one-off migration copies existing campaigns' content into Looply, and a
  cleanup step then deletes the templates that only campaigns used.

## User Stories

### Creating and editing campaigns

1. As a marketer, I want to create a clean campaign by choosing a layout, so that my email starts with our brand's header and footer without any copy-pasting.
2. As a marketer, I want to duplicate an existing campaign, so that I can reuse a past email's content, layout, subject, sender and audience as a starting point.
3. As a marketer, I want a duplicated campaign to start as a fresh draft with no send history or engagement numbers, so that its stats aren't confused with the original's.
4. As a marketer, I want a duplicated campaign to be named "Copy of <original>" by default, so that I can tell the two apart right away.
5. As a marketer, I want to edit a campaign's body, subject, sender and template variables in Looply, so that everything about the campaign is in one place.
6. As a marketer, I want to change a draft campaign's layout, so that I can restyle an email without rewriting it.
7. As a marketer, I want saving a campaign to never create anything in Sendly, so that abandoned or deleted drafts leave nothing behind.
8. As a marketer, I want deleting a campaign to delete its content too, so that I don't have to clean up anywhere else.
9. As a marketer, I want to see a list of available layouts with their names when I create a campaign, so that I can pick the right one.

### Previewing

10. As a marketer, I want to preview my campaign's body inside its layout, so that I can see what recipients will actually receive.
11. As a marketer, I want the preview to fill in template variables, so that I can check personalization before sending.
12. As a marketer, I want the preview to use the same rendering engine as the real send, so that what I approve is what goes out.
13. As a marketer, I want the preview to tell me which variables are missing, so that I can fix them before sending instead of finding out afterwards.
14. As a marketer, I want the preview to show the rendered subject line, so that I can check personalization in the subject.

### Sending

15. As a marketer, I want to be blocked from sending a campaign that has no layout, so that no unbranded email goes out by accident.
16. As a marketer, I want to be blocked from sending a campaign that has no body, so that no empty email goes out.
17. As a marketer, I want a send that references a deleted layout to fail clearly, so that no email goes out half-styled.
18. As a marketer, I want every recipient of one campaign to get the same layout version even if someone edits the layout during the send, so that the campaign looks consistent.
19. As a marketer, I want subject lines like "Hi ${first_name}" to keep working, so that personalized subjects behave the same as before.
20. As a marketer, I want layout fixes to show up in my draft campaigns automatically, so that I never send an email with an outdated header or footer.
21. As a marketer, I want a sent campaign to keep the exact layout it was sent with, so that later layout edits don't change the record of what went out.

### Sendly hygiene

22. As a Sendly admin, I want the template list to contain only templates people created on purpose, so that I can find and maintain them.
23. As a Sendly admin, I want existing campaign-only templates removed after their content has been safely moved, so that the current clutter goes away and doesn't just stop growing.
24. As a Sendly admin, I want to review the list of templates before any are deleted, so that a template something else still uses isn't deleted.
25. As a Sendly admin, I want layouts to stay the single source of brand chrome, so that one layout edit updates every draft that uses it.

### Migration

26. As an operator, I want a backfill that copies each existing campaign's template content into the campaign, so that old campaigns no longer depend on Sendly templates.
27. As an operator, I want the backfill to have a dry-run mode, so that I can see what it would change before it writes anything.
28. As an operator, I want the backfill to be safe to re-run, so that a partial failure can be resumed.
29. As an operator, I want the backfill to compare the template rendering with the inline rendering for each campaign and flag differences, so that I find content that would render differently before deleting the templates.
30. As an operator, I want the backfill to list migrated draft campaigns that have no layout, so that someone can assign one before they need to send.
31. As an operator, I want the backfill to output the set of Sendly templates referenced only by campaigns, so that cleanup has an exact, reviewable list.

### Integrators

32. As a developer using Sendly's broadcast API, I want to send inline HTML with a layout reference, so that I don't need a template for one-off content.
33. As a developer, I want a Sendly render endpoint, so that any client can preview content the same way Sendly sends it.
34. As a developer using the Python SDK, I want `layout_id`/`layout_alias` on broadcast requests and a render method, so that I don't have to call the raw HTTP API.

## Implementation Decisions

### Ownership

- Looply owns campaign content (subject, HTML body, template variables, from
  email, layout reference). Sendly owns layouts. Looply campaigns no longer
  use Sendly templates in any way.
- Private or hidden templates in Sendly were considered and rejected. They
  hide the clutter instead of preventing it, and they need extra ownership
  and cleanup rules.
- Copying the layout's HTML into each campaign was also rejected, because
  layout fixes would never reach existing campaigns.

### Sendly: rendering (deep module)

- Extend `EmailRenderingService` with one content-rendering operation that
  takes a body, a subject, an optional layout (already resolved to its HTML)
  and variables, and returns the rendered HTML and subject. Both the template
  path and the inline path call it, so their behavior (layout wrapping with
  `content=`, Mako rendering of the subject, the default `year` variable,
  error reporting for missing variables) can't drift apart.
- Inline sends now render the subject with Mako, the same way the template
  path already does.
- The template path's existing behavior for a deleted layout stays as it is:
  log a warning and send without the layout. Only the inline path rejects.

### Sendly: inline layout on broadcasts

- `BroadcastCreateRequest` gains optional `layout_id` and `layout_alias`.
  They're only valid with inline `html`. Combining them with a template
  reference is a conflicting-content validation error.
- When the broadcast is accepted, `validate()` resolves the layout reference.
  If the layout doesn't exist or is soft-deleted, the broadcast is rejected
  with a 4xx error before anything is queued.
- `ContentSpec` gains a `layout_html` snapshot, filled in once at accept
  time. The prepare stage renders from this snapshot and never looks the
  layout up again. That guarantees every chunk of a batch uses the same
  layout version, and the sent content can be reproduced from the batch.
- The layout reference (`layout_id`) is also kept in `ContentSpec`, so you
  can still see where the content came from.
- Single-send `/emails` may get the same inline-layout support, because it
  shares the rendering service. It isn't needed for this PRD.

### Sendly: render endpoint

- New `POST /render` that accepts `{html, subject, layout_id | layout_alias,
  template_variables}` and returns `{html, subject}`. It goes through the same
  rendering operation as sending.
- Missing variables and Mako syntax errors return a 422 with the existing
  descriptive message, which names the missing variables.
- It has no side effects and no persistence. It is protected by a read
  permission on layouts.

### tessera-sdk-py

- `SendBroadcastRequest` gains `layout_id` and `layout_alias`.
- The Sendly client gains a `render()` method that matches the endpoint.
- The SDK must be released before Looply can send with a layout.

### Looply: campaign schema

- `Campaign` gains `html` (text, nullable for drafts) and `layout_id` (UUID
  of the Sendly layout, nullable for drafts, not a foreign key because it
  lives in Sendly's domain, like `project_id`). `subject`, `from_email` and
  `template_variables` stay as they are.
- `template_id` stays in the schema as read-only during the migration and is
  removed in a follow-up migration once the backfill and cleanup are done.
  New and updated campaigns never set it.
- The campaign API (create, read and update schemas) exposes `html` and
  `layout_id`.

### Looply: sending

- `SendCampaignCommand` builds the broadcast from the campaign's own content:
  inline `html`, `subject`, `layout_id`, `template_variables` and
  `from_email`. It no longer sends `template_id`.
- On top of the checks it already does, it rejects a campaign that has no
  `layout_id` or no `html`, with a clear validation error, before any recipients
  are resolved or Sendly is called.
- A Sendly rejection because of a deleted layout goes through the existing
  send failure path (the campaign is marked `failed`).

### Looply: duplicate

- New `DuplicateCampaignCommand` and endpoint. It copies the name (as "Copy
  of <name>"), segment, project, subject, html, layout_id,
  template_variables, from_email and tags into a new `draft` campaign owned
  by the current user.
- It resets the status, batch_id, the sent and completed timestamps, all
  engagement counts, the polling fields and the recipients.
- Any campaign can be duplicated, whatever its status.

### Looply: backfill (one-off)

- An operator-run, idempotent command with a dry-run mode. For each campaign
  that has a `template_id` and no `html`, it fetches the template from
  Sendly. It then copies the template's `html`, its `subject` (unless the
  campaign already overrides it), its `layout_id`, and its `from_email`
  (unless the campaign already has one).
- For each campaign it calls `render` both ways and reports any
  differences: the template rendering, and the inline content with the layout.
- It reports draft campaigns that end up with no layout, because they can't
  be sent until someone assigns one.
- It outputs the cleanup list: templates referenced by migrated campaigns
  and not used by anything else that can be detected. Templates are deleted
  in a separate, manual step after someone reviews that list. The backfill
  never deletes anything.

### looply-portal

- The new-campaign modal offers two options: **Clean** (a required layout
  picker that lists Sendly layouts) and **Duplicate campaign** (a campaign
  picker). The template list and the creation of scratch templates are
  removed.
- The campaign form reads and writes `html`, `subject`, `layout_id` and so on
  through Looply's campaign API. It no longer calls Sendly's template
  create, update or clone endpoints.
- The form includes a layout selector and a preview pane backed by Sendly's
  `/render`.
- Users without permission to list layouts see the same kind of
  inline "no access" message the template list uses today.

### Rollout order

1. Sendly: rendering refactor, inline layout + snapshot, `/render`.
2. tessera-sdk-py: request fields + `render()`, then a release.
3. Looply: schema + API, send command, duplicate command.
4. looply-portal: modal, form, preview.
5. Backfill (dry run, review, real run), then review the cleanup list and
   delete the Sendly templates, then drop `Campaign.template_id`.

## Testing Decisions

- Tests check external behavior through public interfaces (the service
  methods, the commands, HTTP endpoints). They assert on the rendered output,
  on validation errors and on the request sent to Sendly, not on how things
  work internally. Looply tests must run with `ENV=test`.
- **Sendly, rendering and accept** (in scope):
  - Rendering: inline body wrapped in a layout; inline subject rendered with
    variables; the template path's output is unchanged after the refactor;
    missing variables named in the error.
    Prior art: the existing `EmailRenderingService` service tests.
  - Broadcast accept: inline + layout is accepted and `layout_html` is
    saved in the content spec; a layout reference combined with a template
    reference is rejected; a missing or soft-deleted layout is rejected
    before queuing; editing the layout after accept doesn't change what the
    prepare stage renders. Prior art: the existing send-broadcast command and
    broadcast router tests.
  - `/render`: happy path, missing-variable 422, unknown layout 4xx.
    Prior art: the existing layout and template router tests.
- **Looply, send and duplicate** (in scope):
  - `SendCampaignCommand`: the Sendly request carries inline html, subject,
    layout_id and variables, with no template_id; it rejects a campaign
    without a layout or html before calling Sendly; a Sendly rejection marks
    the campaign failed. Prior art: the existing send-campaign command tests
    with a mocked Sendly client.
  - Duplicate: every content field is copied, the status, counts, timestamps,
    batch_id and recipients are reset, the "Copy of" name is used, and tags
    are copied. Prior art: the campaign router tests and campaign fixtures.
- **Not covered by automated tests in this PRD**: the backfill command (it
  is run once, checked with its dry run and its comparison report) and
  the portal UI.

## Out of Scope

- Hidden, private or owned templates in Sendly.
- Reusable content templates owned by Looply. Reuse happens by duplicating
  campaigns.
- Offering Sendly templates as a starting point in Looply.
- Project-scoping layouts in Sendly. Layouts stay global.
- Preventing deletion of a layout that drafts still use. A deleted layout
  shows up when the send is rejected and in the preview.
- Inline layouts on Sendly's single-send `/emails` endpoint, beyond what
  sharing the rendering service makes possible for free.
- Automatically deleting Sendly templates. Cleanup is a separate manual
  step that runs after review.
- Version history for layouts.

## Further Notes

- Because of the subject-rendering change, an inline subject that contains a
  literal `${` now gets rendered with Mako. That's acceptable. The backfill's
  comparison report shows any cases among migrated campaigns.
- Migrated drafts whose source template had no layout can't be sent until
  someone assigns a layout, because a layout is now required to send.
  Campaigns that were already sent aren't affected.
- Sendly's broadcast batches are the record of what was sent. With the
  layout snapshot, a batch's content spec now holds everything needed to
  re-render the email, not only a template reference that could have changed
  since.
- Dropping `Campaign.template_id` is a follow-up migration after cleanup.
  Until then it's kept only so the backfill can read it.

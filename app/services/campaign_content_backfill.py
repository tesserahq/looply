"""Planning for the one-off backfill of campaign content out of legacy
per-campaign Sendly templates (docs/prds/0007-campaign-owned-email-content.md).

Pure: no database and no Sendly calls of its own. scripts/backfill_campaign_content.py
reads campaigns, fetches each template, and hands both to plan_campaign_backfill()
along with a render function, then applies the resulting updates. Keeping the
decisions here makes them testable without a database or network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from uuid import UUID

from app.constants.campaign import CampaignStatus

# Stand-ins for the per-recipient fields Sendly merges into the variables at
# send time (see SendCampaignCommand._to_broadcast_recipient), so a
# personalized email renders instead of failing on ${first_name}.
SAMPLE_RECIPIENT_VARIABLES = {
    "first_name": "Jane",
    "last_name": "Doe",
    "company": "Acme",
    "job_title": "Head of Marketing",
    "contact_type": "person",
}

# Aliases the old portal generated for per-campaign templates:
# "Start from scratch" -> `template-<base36 timestamp>`.
_SCRATCH_ALIAS = re.compile(r"^template-[0-9a-z]+$")


@dataclass(frozen=True)
class CampaignSnapshot:
    id: UUID
    name: str
    status: str
    template_id: UUID
    subject: Optional[str]
    from_email: Optional[str]
    layout_id: Optional[UUID]
    template_variables: dict[str, Any]
    deleted: bool = False
    # Already has html of its own (e.g. edited in the portal since): nothing
    # to copy, but its template still belongs on the cleanup list.
    migrated: bool = False


@dataclass(frozen=True)
class TemplateSnapshot:
    id: UUID
    alias: str
    name: Optional[str]
    subject: str
    html: str
    from_email: Optional[str]
    layout_id: Optional[UUID]
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Rendered:
    html: str
    subject: str


class RenderFailure(Exception):
    def __init__(self, status_code: Optional[int], message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


# (html, subject, layout_id, variables) -> Rendered, raising RenderFailure.
RenderFn = Callable[[str, str, Optional[UUID], dict[str, Any]], Rendered]


@dataclass
class BackfillPlan:
    campaign_id: UUID
    template_id: UUID
    updates: dict[str, Any]
    findings: list[str] = field(default_factory=list)


def plan_campaign_backfill(
    campaign: CampaignSnapshot, template: TemplateSnapshot, render: RenderFn
) -> BackfillPlan:
    """Decide what to copy from `template` onto `campaign`, and what a human
    should look at before the copy is trusted.

    Copies the template's html and subject, plus its layout and sender
    unless the campaign already has its own. The template's subject wins
    over the campaign's: Sendly's template path always rendered the
    template subject and ignored the request's, so that's what was (or
    would have been) sent — a differing campaign subject is reported.
    """
    findings: list[str] = []

    if campaign.subject and campaign.subject != template.subject:
        findings.append(
            f"subject_mismatch: campaign had {campaign.subject!r}; using the "
            f"template's {template.subject!r}, which is what Sendly sends for a "
            "templated campaign"
        )

    layout_id = campaign.layout_id or template.layout_id
    updates = {
        "html": template.html,
        "subject": template.subject,
        "layout_id": layout_id,
        "from_email": campaign.from_email or template.from_email,
    }

    is_draft = campaign.status == CampaignStatus.DRAFT.value and not campaign.deleted
    if layout_id is None and is_draft:
        findings.append(
            "no_layout: draft has no layout; assign one before it can be sent"
        )

    variables = {**campaign.template_variables, **SAMPLE_RECIPIENT_VARIABLES}
    before = _render_like_template_path(template, variables, render, findings)
    after = _try_render(
        render, updates["html"], updates["subject"], layout_id, variables
    )
    if isinstance(after, RenderFailure):
        findings.append(_describe("after", after))
    elif before is not None and after != before:
        findings.append(
            "render_mismatch: the inline rendering differs from the template "
            "rendering"
        )

    return BackfillPlan(
        campaign_id=campaign.id,
        template_id=template.id,
        updates=updates,
        findings=findings,
    )


def _render_like_template_path(
    template: TemplateSnapshot,
    variables: dict[str, Any],
    render: RenderFn,
    findings: list[str],
) -> Optional[Rendered]:
    """Render the way Sendly's template path did, including its fallback of
    sending unwrapped when the template's layout was deleted."""
    result = _try_render(
        render, template.html, template.subject, template.layout_id, variables
    )
    if (
        isinstance(result, RenderFailure)
        and result.status_code == 404
        and template.layout_id is not None
    ):
        findings.append(
            f"layout_deleted: layout {template.layout_id} no longer exists; the "
            "template path sent unwrapped, an inline send will be rejected until "
            "another layout is picked"
        )
        result = _try_render(render, template.html, template.subject, None, variables)
    if isinstance(result, RenderFailure):
        findings.append(_describe("before", result))
        return None
    return result


def _try_render(
    render: RenderFn,
    html: str,
    subject: str,
    layout_id: Optional[UUID],
    variables: dict[str, Any],
) -> Rendered | RenderFailure:
    try:
        return render(html, subject, layout_id, variables)
    except RenderFailure as e:
        return e


def _describe(label: str, failure: RenderFailure) -> str:
    return f"render_error ({label}): {failure.status_code} {failure.message}"


def classify_template_for_cleanup(template: TemplateSnapshot) -> str:
    """'auto-generated' for templates the old portal created per campaign
    (safe to delete once their content is copied); 'curated' for anything
    else — a real template a campaign was started from. Those were edited in
    place by the old flow but are still someone's template: keep them."""
    if _SCRATCH_ALIAS.match(template.alias):
        return "auto-generated"
    if any(tag.startswith("campaign:") for tag in template.tags):
        return "auto-generated"
    if (template.name or "").startswith("Campaign: "):
        return "auto-generated"
    return "curated"

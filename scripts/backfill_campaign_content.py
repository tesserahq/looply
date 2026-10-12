#!/usr/bin/env python3
"""One-off: copy each campaign's legacy Sendly template content onto the
campaign itself (docs/prds/0007-campaign-owned-email-content.md, issue #178).

    ENV=<env> poetry run python scripts/backfill_campaign_content.py            # dry run
    ENV=<env> poetry run python scripts/backfill_campaign_content.py --apply

Dry run by default: writes nothing, prints a summary, and writes a JSON
report (--report, default backfill_campaign_content_report.json) with, per
campaign, the fields it would copy and anything to review first
(subject_mismatch, no_layout, layout_deleted, render_error,
render_mismatch), plus the cleanup list of referenced templates classified
auto-generated vs curated. It never deletes anything in Sendly.

Idempotent: only campaigns with a template_id and no html are touched, and
--apply re-checks that per row, so re-running after a partial run (or after
someone edited a campaign in the portal, which migrates it) is safe.

Phases: one short read session, then all Sendly calls with no transaction
open, then one short write session. The service account needs read access
to Sendly templates and layouts (/render is gated on layout read).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tessera_sdk import TesseraError  # noqa: E402
from tessera_sdk.clients.sendly import RenderRequest, SendlyClient  # noqa: E402

from app.db import session_scope  # noqa: E402
from app.integrations.sendly_client_factory import build_sendly_client  # noqa: E402
from app.models.campaign import Campaign  # noqa: E402
from app.services.campaign_content_backfill import (  # noqa: E402
    BackfillPlan,
    CampaignSnapshot,
    RenderFailure,
    Rendered,
    TemplateSnapshot,
    classify_template_for_cleanup,
    plan_campaign_backfill,
)

logger = logging.getLogger("backfill_campaign_content")


def read_campaigns() -> list[CampaignSnapshot]:
    """Every campaign that references a template, soft-deleted and already
    migrated ones included: only live, unmigrated campaigns get planned, but
    every referenced template belongs on the cleanup list (deleted
    campaigns' templates are most of the clutter)."""
    with session_scope() as db:
        rows = (
            db.query(Campaign)
            .execution_options(skip_soft_delete_filter=True)
            .filter(Campaign.template_id.isnot(None))
            .all()
        )
        return [
            CampaignSnapshot(
                id=row.id,
                name=row.name,
                status=row.status,
                template_id=row.template_id,
                subject=row.subject,
                from_email=row.from_email,
                layout_id=row.layout_id,
                template_variables=dict(row.template_variables or {}),
                deleted=row.deleted_at is not None,
                migrated=bool(row.html),
            )
            for row in rows
        ]


def fetch_templates(
    sendly: SendlyClient, template_ids: set[UUID]
) -> tuple[dict[UUID, TemplateSnapshot], dict[UUID, str]]:
    templates: dict[UUID, TemplateSnapshot] = {}
    missing: dict[UUID, str] = {}
    for template_id in sorted(template_ids, key=str):
        try:
            t = sendly.get_template(str(template_id))
        except TesseraError as e:
            missing[template_id] = str(e)
            continue
        templates[template_id] = TemplateSnapshot(
            id=t.id,
            alias=t.alias,
            name=t.name,
            subject=t.subject,
            html=t.html,
            from_email=t.from_email,
            layout_id=t.layout_id,
            tags=list(t.tags or []),
        )
    return templates, missing


def make_render(sendly: SendlyClient):
    def render(
        html: str, subject: str, layout_id: Optional[UUID], variables: dict[str, Any]
    ) -> Rendered:
        try:
            result = sendly.render(
                RenderRequest(
                    html=html,
                    subject=subject,
                    layout_id=layout_id,
                    template_variables=variables,
                )
            )
        except TesseraError as e:
            raise RenderFailure(getattr(e, "status_code", None), str(e)) from e
        return Rendered(html=result.html, subject=result.subject)

    return render


def apply_plans(plans: list[BackfillPlan]) -> int:
    applied = 0
    with session_scope() as db:
        for plan in plans:
            campaign = (
                db.query(Campaign).filter(Campaign.id == plan.campaign_id).first()
            )
            # Re-checked at write time: skip anything migrated since the read
            # (e.g. edited in the portal, which writes html).
            if campaign is None or campaign.html:
                continue
            for key, value in plan.updates.items():
                setattr(campaign, key, value)
            applied += 1
    return applied


def build_report(
    campaigns: list[CampaignSnapshot],
    plans: list[BackfillPlan],
    templates: dict[UUID, TemplateSnapshot],
    missing: dict[UUID, str],
) -> dict[str, Any]:
    by_template: dict[UUID, list[CampaignSnapshot]] = defaultdict(list)
    for campaign in campaigns:
        by_template[campaign.template_id].append(campaign)
    names = {c.id: c.name for c in campaigns}
    statuses = {c.id: c.status for c in campaigns}

    cleanup = []
    for template_id, refs in by_template.items():
        template = templates.get(template_id)
        cleanup.append(
            {
                "template_id": str(template_id),
                "alias": template.alias if template else None,
                "name": template.name if template else None,
                "classification": (
                    classify_template_for_cleanup(template) if template else "missing"
                ),
                "referenced_by": [
                    {
                        "campaign_id": str(c.id),
                        "name": c.name,
                        "deleted": c.deleted,
                        "migrated": c.migrated,
                    }
                    for c in refs
                ],
            }
        )

    return {
        "campaigns": [
            {
                "campaign_id": str(plan.campaign_id),
                "name": names[plan.campaign_id],
                "status": statuses[plan.campaign_id],
                "template_id": str(plan.template_id),
                "updates": {
                    "html_length": len(plan.updates["html"]),
                    "subject": plan.updates["subject"],
                    "layout_id": (
                        str(plan.updates["layout_id"])
                        if plan.updates["layout_id"]
                        else None
                    ),
                    "from_email": plan.updates["from_email"],
                },
                "findings": plan.findings,
            }
            for plan in plans
        ],
        "missing_templates": {str(k): v for k, v in missing.items()},
        "cleanup": sorted(
            cleanup, key=lambda c: (c["classification"], c["alias"] or "")
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--apply", action="store_true", help="write the changes (default: dry run)"
    )
    parser.add_argument(
        "--report",
        default="backfill_campaign_content_report.json",
        help="where to write the JSON report",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    campaigns = read_campaigns()
    sendly = build_sendly_client()
    templates, missing = fetch_templates(sendly, {c.template_id for c in campaigns})
    render = make_render(sendly)

    plans = [
        plan_campaign_backfill(c, templates[c.template_id], render)
        for c in campaigns
        if not c.deleted and not c.migrated and c.template_id in templates
    ]

    report = build_report(campaigns, plans, templates, missing)
    Path(args.report).write_text(json.dumps(report, indent=2))

    flagged = [p for p in plans if p.findings]
    auto = sum(1 for c in report["cleanup"] if c["classification"] == "auto-generated")
    logger.info(
        "%d campaign(s) to migrate, %d with findings to review; %d template(s) "
        "missing in Sendly; cleanup: %d auto-generated / %d referenced template(s). "
        "Report: %s",
        len(plans),
        len(flagged),
        len(missing),
        auto,
        len(report["cleanup"]),
        args.report,
    )

    if not args.apply:
        logger.info("Dry run: nothing written. Re-run with --apply to migrate.")
        return 0

    applied = apply_plans(plans)
    logger.info("Applied to %d campaign(s).", applied)
    return 0


if __name__ == "__main__":
    sys.exit(main())

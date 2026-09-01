"""Celery task: ingest a single Linden domain event received over NATS.

Mirrors orcha's process_nats_event_task split (~/sites/linden-family/orcha) - the
NATS handler in run_nats_worker.py only dispatches the raw message dict here via
.delay(msg), decoupling the NATS ack from DB work. All envelope parsing, Contact
upsert, and CustomEvent creation happens in this task.

Looply's NATS subscription sees every event type on the shared stream (subscribed
via "com.>"), not just contact-relevant ones. An event whose type has no
EventMapping row is dropped up front - no Contact resolution/auto-create, no
CustomEvent row, no EventFieldMapping applied - so untracked traffic never causes
DB writes or junk contacts.

Contact identity and attribute population are both driven by EventMapping (the
parent registration, holding identity configuration) and its EventFieldMapping
children (non-identity attributes), resolved once per event via
app.services.event_mapping_resolver - which payload path identifies the contact
(and whether that's a Contact.external_id or .email lookup), and which paths
fill in built-in Contact fields vs. custom fields, are all operator-configured
per event_type rather than hardcoded to a single envelope shape. See
docs/prds/0003-event-driven-contact-resolution.md and
docs/prds/0004-event-mapping-consolidation.md.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.repositories.custom_event_repository import CustomEventRepository
from app.repositories.contact_custom_field_value_repository import (
    ContactCustomFieldValueRepository,
    CustomFieldValueTypeError,
    UndefinedCustomFieldError,
)
from app.repositories.contact_repository import ContactRepository
from app.repositories.event_field_mapping_repository import (
    EventFieldMappingRepository,
)
from app.repositories.event_mapping_repository import EventMappingRepository
from app.services.event_mapping_resolver import resolve as resolve_event_mappings
from app.utils.db.db_session_helper import db_session

logger = logging.getLogger(__name__)


def _parse_occurred_at(time_value) -> datetime:
    """Parse the envelope's `time` field, falling back to now() if absent/malformed."""
    if isinstance(time_value, str):
        try:
            return datetime.fromisoformat(time_value.replace("Z", "+00:00"))
        except ValueError:
            logger.warning(f"Could not parse event time {time_value!r}, using now()")
    return datetime.now(timezone.utc)


def _apply_custom_field_values(
    db: Session, contact_id, custom_field_values: dict
) -> None:
    """
    Write every resolved custom_field mapping value onto the contact. A value that
    doesn't match its target field's locked value_type is skipped and logged -
    there's no caller on this ingestion path to reject the write back to, so a bad
    mapping/payload must not block the CustomEvent itself from being recorded, or
    stop other values for the same event from applying.
    """
    field_value_repository = ContactCustomFieldValueRepository(db)
    for field_name, value in custom_field_values.items():
        try:
            field_value_repository.set_value(
                contact_id=contact_id,
                field_name=field_name,
                value=value,
                set_by_user_id=None,
            )
        except (UndefinedCustomFieldError, CustomFieldValueTypeError) as e:
            logger.warning(
                f"Custom field mapping could not be applied "
                f"(field={field_name!r}, value={value!r}): {e}"
            )


def _process_nats_event(db: Session, msg: Dict) -> Optional[str]:
    """
    Process a single CloudEvents-shaped envelope received over NATS: if its
    event_type has a registered EventMapping, resolve (or auto-create) the
    Contact identified by that EventMapping's identity configuration, then
    record a CustomEvent against it.

    Only event_type, time, and event_data are read from the envelope for
    ingestion - the rest (source, spec_version, subject, tags, labels, user,
    the envelope's own id) is stored verbatim in raw_envelope for audit, per the
    PRD. Contact identity/attributes come entirely from event_data via
    EventMapping/EventFieldMapping - there is deliberately no hardcoded envelope
    field read for identity anymore (see
    docs/prds/0003-event-driven-contact-resolution.md for why the previous
    hardcoded top-level `user` read was wrong).

    Args:
        db: Database session.
        msg: The raw event envelope, as received from NATS.

    Returns:
        The created CustomEvent's id as a string, or None if event_type isn't
        tracked, has no configured identity-key mapping, or that mapping's
        source_path didn't resolve for this event.
    """
    event_type = msg.get("event_type", "")
    event_mapping = EventMappingRepository(db).get_by_event_type(event_type)
    if not event_mapping:
        logger.debug(f"Dropping untracked event_type {event_type!r}")
        return None

    occurred_at = _parse_occurred_at(msg.get("time"))
    event_data = msg.get("event_data")
    if not isinstance(event_data, dict):
        event_data = {} if event_data is None else {"data": event_data}

    field_mappings = EventFieldMappingRepository(db).get_mappings_for_event_mapping(
        event_mapping.id
    )
    resolved = resolve_event_mappings(event_mapping, field_mappings, event_data)
    if not resolved.has_identity:
        logger.error(
            "Dropping NATS event: no identity configured for event_type "
            f"{event_type!r}, or its identity_source_path didn't resolve: {msg}"
        )
        return None

    contact = ContactRepository(db).get_or_create_from_event(
        identity_field=resolved.identity_field,
        identity_value=resolved.identity_value,
        contact_field_values=resolved.contact_field_values,
        source=event_mapping.source,
        default_status=event_mapping.default_status,
        default_tags=event_mapping.default_tags,
    )

    event = CustomEventRepository(db).create_event(
        contact_id=contact.id,
        name=event_type,
        occurred_at=occurred_at,
        properties=event_data,
        raw_envelope=msg,
    )

    _apply_custom_field_values(db, contact.id, resolved.custom_field_values)

    logger.info(
        f"Recorded event {event_type!r} for contact {contact.id} "
        f"({resolved.identity_field}={resolved.identity_value})"
    )
    return str(event.id)


@celery_app.task(name="app.tasks.process_nats_event_task.process_nats_event_task")
def process_nats_event_task(msg: Dict) -> Optional[str]:
    """Celery entry point - opens its own session and delegates to _process_nats_event
    (called directly with the test db fixture in tests, no live NATS needed)."""
    with db_session() as db:
        return _process_nats_event(db, msg)

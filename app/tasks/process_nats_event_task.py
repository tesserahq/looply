"""Celery task: ingest a single Linden domain event received over NATS.

Mirrors orcha's process_nats_event_task split (~/sites/linden-family/orcha) - the
NATS handler in run_nats_worker.py only dispatches the raw message dict here via
.delay(msg), decoupling the NATS ack from DB work. All envelope parsing, Contact
upsert, and CustomEvent creation happens in this task.

Looply's NATS subscription sees every event type on the shared stream (subscribed
via "com.>"), not just contact-relevant ones. An event whose type isn't registered
in TrackedEventType is dropped up front - no Contact resolution/auto-create, no
CustomEvent row, no EventFieldMapping applied - so untracked traffic never causes
DB writes or junk contacts.

Also applies any EventFieldMapping rows matching the event's type - a host-
configured way to derive a Custom Field value directly from a field in the event's
event_data (e.g. "person.created" -> event_data.account.family_member_count ->
the "family_member_count" field), on top of the PRD's own event/field primitives.

See docs/prds/0002-contact-custom-fields-and-events.md, "Custom Events".
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
from app.repositories.tracked_event_type_repository import (
    TrackedEventTypeRepository,
)
from app.utils.db.db_session_helper import db_session

logger = logging.getLogger(__name__)

_MISSING = object()


def _parse_occurred_at(time_value) -> datetime:
    """Parse the envelope's `time` field, falling back to now() if absent/malformed."""
    if isinstance(time_value, str):
        try:
            return datetime.fromisoformat(time_value.replace("Z", "+00:00"))
        except ValueError:
            logger.warning(f"Could not parse event time {time_value!r}, using now()")
    return datetime.now(timezone.utc)


def _extract_by_path(data: dict, path: str):
    """Resolve a dot-path (e.g. "account.family_member_count") against a nested
    dict, returning _MISSING if any segment is absent or an intermediate value
    isn't a dict."""
    current = data
    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return _MISSING
        current = current[segment]
    return current


def _apply_field_mappings(
    db: Session, contact_id, event_type: str, event_data: dict
) -> None:
    """
    Apply every active EventFieldMapping matching event_type: extract the value at
    each mapping's source_path from event_data and write it to the target custom
    field. A mapping that doesn't resolve (missing path) or whose extracted value
    doesn't match the target field's locked value_type is skipped and logged -
    there's no caller on this ingestion path to reject the write back to, so a bad
    mapping/payload must not block the CustomEvent itself from being recorded, or
    stop other mappings for the same event from applying.
    """
    mappings = EventFieldMappingRepository(db).get_mappings_for_event_type(event_type)
    if not mappings:
        return

    field_value_repository = ContactCustomFieldValueRepository(db)
    for mapping in mappings:
        value = _extract_by_path(event_data, mapping.source_path)
        if value is _MISSING:
            logger.debug(
                f"EventFieldMapping {mapping.id}: source_path "
                f"{mapping.source_path!r} not found in event_data, skipping"
            )
            continue

        try:
            field_value_repository.set_value(
                contact_id=contact_id,
                field_name=mapping.field_name,
                value=value,
                set_by_user_id=None,
            )
        except (UndefinedCustomFieldError, CustomFieldValueTypeError) as e:
            logger.warning(
                f"EventFieldMapping {mapping.id} could not be applied "
                f"(field={mapping.field_name!r}, value={value!r}): {e}"
            )


def _process_nats_event(db: Session, msg: Dict) -> Optional[str]:
    """
    Process a single CloudEvents-shaped envelope received over NATS: if its
    event_type is tracked, resolve (or auto-create) the Contact identified by the
    envelope's embedded `user.id`, then record a CustomEvent against it.

    Only event_type, time, event_data, and user are read from the envelope for
    ingestion - the rest (source, spec_version, subject, tags, labels, the
    envelope's own id) is stored verbatim in raw_envelope for audit, per the PRD.

    Args:
        db: Database session.
        msg: The raw event envelope, as received from NATS.

    Returns:
        The created CustomEvent's id as a string, or None if event_type isn't
        tracked or the envelope had no usable user identity.
    """
    event_type = msg.get("event_type", "")
    if not TrackedEventTypeRepository(db).get_by_event_type(event_type):
        logger.debug(f"Dropping untracked event_type {event_type!r}")
        return None

    user = msg.get("user") or {}
    external_id = user.get("id")
    if not external_id:
        logger.error(f"Dropping NATS event with no embedded user.id: {msg}")
        return None

    occurred_at = _parse_occurred_at(msg.get("time"))
    event_data = msg.get("event_data")
    if not isinstance(event_data, dict):
        event_data = {} if event_data is None else {"data": event_data}

    contact = ContactRepository(db).get_or_create_from_event_user(
        external_id=external_id,
        email=user.get("email"),
        first_name=user.get("first_name"),
        last_name=user.get("last_name"),
    )

    event = CustomEventRepository(db).create_event(
        contact_id=contact.id,
        name=event_type,
        occurred_at=occurred_at,
        properties=event_data,
        raw_envelope=msg,
    )

    _apply_field_mappings(db, contact.id, event_type, event_data)

    logger.info(
        f"Recorded event {event_type!r} for contact {contact.id} "
        f"(external_id={external_id})"
    )
    return str(event.id)


@celery_app.task(name="app.tasks.process_nats_event_task.process_nats_event_task")
def process_nats_event_task(msg: Dict) -> Optional[str]:
    """Celery entry point - opens its own session and delegates to _process_nats_event
    (called directly with the test db fixture in tests, no live NATS needed)."""
    with db_session() as db:
        return _process_nats_event(db, msg)

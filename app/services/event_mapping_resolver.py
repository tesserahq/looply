"""Resolves an EventMapping (plus its EventFieldMapping children) against an
ingested event's event_data - the deep module behind NATS event ingestion's
contact-identity and field-population logic (see
docs/prds/0003-event-driven-contact-resolution.md and
docs/prds/0004-event-mapping-consolidation.md).

Deliberately dependency-free: no DB session, no model writes. Given the
EventMapping row and its active children already fetched by the caller and a
plain event_data dict, it just resolves dot-paths and buckets the results -
everything a caller (app.tasks.process_nats_event_task) needs to know before it
touches the database.
"""

from dataclasses import dataclass, field
from typing import Any, List, Literal, Optional

from app.models.event_field_mapping import EventFieldMapping
from app.models.event_mapping import EventMapping

_MISSING = object()

IdentityField = Literal["external_id", "email"]


def extract_by_path(data: dict, path: str) -> Any:
    """Resolve a dot-path (e.g. "person.account.family_member_count") against a
    nested dict, returning _MISSING if any segment is absent or an intermediate
    value isn't a dict."""
    current = data
    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return _MISSING
        current = current[segment]
    return current


@dataclass
class ResolvedEventMappings:
    """The result of resolving one EventMapping (identity + attribute children)
    against one event's event_data."""

    identity_field: Optional[IdentityField] = None
    identity_value: Optional[Any] = None
    contact_field_values: dict = field(default_factory=dict)
    custom_field_values: dict = field(default_factory=dict)

    @property
    def has_identity(self) -> bool:
        """False when the EventMapping has no identity configured, or its
        identity_source_path didn't resolve for this event - either way, the
        caller has no contact to resolve/create and must drop the event."""
        return self.identity_value is not None


def resolve(
    event_mapping: EventMapping,
    field_mappings: List[EventFieldMapping],
    event_data: dict,
) -> ResolvedEventMappings:
    """Resolve an EventMapping's identity configuration and its
    EventFieldMapping children's source_paths against event_data, splitting the
    results into the identity key, built-in contact_field values, and
    custom_field values.

    A mapping (identity or attribute) whose source_path doesn't resolve is
    skipped - for an attribute that just means that field isn't set this time;
    for identity it means result.has_identity is False and the caller must drop
    the event, same fail-safe behavior as ingestion has always had.
    """
    result = ResolvedEventMappings()

    if event_mapping.identity_target_field and event_mapping.identity_source_path:
        value = extract_by_path(event_data, event_mapping.identity_source_path)
        if value is not _MISSING:
            result.identity_field = event_mapping.identity_target_field
            result.identity_value = value

    for mapping in field_mappings:
        value = extract_by_path(event_data, mapping.source_path)
        if value is _MISSING:
            continue

        if mapping.target_type == "contact_field":
            result.contact_field_values[mapping.target_field] = value
        else:
            result.custom_field_values[mapping.field_name] = value

    return result

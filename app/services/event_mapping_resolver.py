"""Resolves a list of EventFieldMapping rows against an ingested event's
event_data - the deep module behind NATS event ingestion's contact-identity and
field-population logic (see
docs/prds/0003-event-driven-contact-resolution.md).

Deliberately dependency-free: no DB session, no model writes. Given the mapping
rows already fetched by the caller and a plain event_data dict, it just resolves
dot-paths and buckets the results - everything a caller (app.tasks.
process_nats_event_task) needs to know before it touches the database.
"""

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from app.models.event_field_mapping import EventFieldMapping

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
    """The result of resolving one event_type's mappings against one event's
    event_data."""

    identity_field: Optional[IdentityField] = None
    identity_value: Optional[Any] = None
    contact_field_values: dict = field(default_factory=dict)
    custom_field_values: dict = field(default_factory=dict)

    @property
    def has_identity(self) -> bool:
        """False when the event_type has no is_identity_key mapping, or that
        mapping's source_path didn't resolve for this event - either way, the
        caller has no contact to resolve/create and must drop the event."""
        return self.identity_value is not None


def resolve(
    mappings: list[EventFieldMapping], event_data: dict
) -> ResolvedEventMappings:
    """Resolve every mapping's source_path against event_data, splitting the
    results into the identity key (from the single is_identity_key=True
    mapping, if any), built-in contact_field values, and custom_field values.

    A mapping whose source_path doesn't resolve is skipped - for a non-identity
    mapping that just means that attribute isn't set this time; for the
    identity-key mapping it means result.has_identity is False and the caller
    must drop the event, same fail-safe behavior as ingestion has always had.
    """
    result = ResolvedEventMappings()
    for mapping in mappings:
        value = extract_by_path(event_data, mapping.source_path)
        if value is _MISSING:
            continue

        if mapping.is_identity_key:
            result.identity_field = mapping.target_field
            result.identity_value = value
        elif mapping.target_type == "contact_field":
            result.contact_field_values[mapping.target_field] = value
        else:
            result.custom_field_values[mapping.field_name] = value

    return result

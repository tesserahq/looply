"""Unit tests for EventMappingResolver - pure resolution logic, no DB/model
instances needed. Lightweight stand-ins for EventMapping/EventFieldMapping are
used so these tests never touch the database, per
docs/prds/0003-event-driven-contact-resolution.md and
docs/prds/0004-event-mapping-consolidation.md's Testing Decisions.
"""

from dataclasses import dataclass
from typing import Optional

from app.services.event_mapping_resolver import resolve


@dataclass
class FakeEventMapping:
    """Stands in for an EventMapping row - resolve() only ever reads these
    attributes."""

    identity_target_field: Optional[str] = None
    identity_source_path: Optional[str] = None


@dataclass
class FakeFieldMapping:
    """Stands in for an EventFieldMapping row - resolve() only ever reads these
    attributes."""

    source_path: str
    target_type: str = "custom_field"
    target_field: Optional[str] = None
    _field_name: Optional[str] = None

    @property
    def field_name(self) -> Optional[str]:
        return self._field_name


def _no_identity() -> FakeEventMapping:
    return FakeEventMapping()


def _identity(target_field: str, source_path: str) -> FakeEventMapping:
    return FakeEventMapping(
        identity_target_field=target_field, identity_source_path=source_path
    )


def _custom_field_mapping(source_path: str, field_name: str) -> FakeFieldMapping:
    return FakeFieldMapping(
        source_path=source_path, target_type="custom_field", _field_name=field_name
    )


def _contact_field_mapping(source_path: str, target_field: str) -> FakeFieldMapping:
    return FakeFieldMapping(
        source_path=source_path, target_type="contact_field", target_field=target_field
    )


def test_contact_field_mapping_resolves_into_contact_field_values():
    field_mapping = _contact_field_mapping("person.first_name", "first_name")
    event_data = {"person": {"first_name": "Harry"}}

    result = resolve(_no_identity(), [field_mapping], event_data)

    assert result.contact_field_values == {"first_name": "Harry"}
    assert result.custom_field_values == {}
    assert result.has_identity is False


def test_custom_field_mapping_resolves_into_custom_field_values():
    field_mapping = _custom_field_mapping(
        "person.account.family_member_count", "family_member_count"
    )
    event_data = {"person": {"account": {"family_member_count": 3}}}

    result = resolve(_no_identity(), [field_mapping], event_data)

    assert result.custom_field_values == {"family_member_count": 3}
    assert result.contact_field_values == {}


def test_identity_resolves_identity_field_and_value():
    event_data = {"person": {"id": "abc-123"}}

    result = resolve(_identity("external_id", "person.id"), [], event_data)

    assert result.identity_field == "external_id"
    assert result.identity_value == "abc-123"
    assert result.has_identity is True
    assert result.contact_field_values == {}


def test_missing_path_is_skipped_not_an_error():
    field_mapping = _custom_field_mapping("person.does.not.exist", "some_field")

    result = resolve(_no_identity(), [field_mapping], {"person": {}})

    assert result.custom_field_values == {}


def test_identity_missing_path_leaves_no_identity():
    result = resolve(_identity("external_id", "person.id"), [], {"person": {}})

    assert result.has_identity is False
    assert result.identity_field is None
    assert result.identity_value is None


def test_no_identity_configured_leaves_no_identity():
    field_mapping = _custom_field_mapping("person.name", "some_field")

    result = resolve(_no_identity(), [field_mapping], {"person": {"name": "Harry"}})

    assert result.has_identity is False


def test_multiple_mixed_mappings_all_resolve_independently():
    field_mappings = [
        _contact_field_mapping("person.first_name", "first_name"),
        _custom_field_mapping(
            "person.account.family_member_count", "family_member_count"
        ),
    ]
    event_data = {
        "person": {
            "id": "abc-123",
            "first_name": "Harry",
            "account": {"family_member_count": 3},
        }
    }

    result = resolve(_identity("external_id", "person.id"), field_mappings, event_data)

    assert result.identity_field == "external_id"
    assert result.identity_value == "abc-123"
    assert result.contact_field_values == {"first_name": "Harry"}
    assert result.custom_field_values == {"family_member_count": 3}


def test_no_mappings_returns_empty_result():
    result = resolve(_no_identity(), [], {"person": {"id": "abc-123"}})

    assert result.has_identity is False
    assert result.contact_field_values == {}
    assert result.custom_field_values == {}

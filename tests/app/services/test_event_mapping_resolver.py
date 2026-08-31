"""Unit tests for EventMappingResolver - pure resolution logic, no DB/model
instances needed. A lightweight stand-in for EventFieldMapping is used so these
tests never touch the database, per docs/prds/0003-event-driven-contact-resolution.md's
Testing Decisions.
"""

from dataclasses import dataclass
from typing import Optional

from app.services.event_mapping_resolver import resolve


@dataclass
class FakeMapping:
    """Stands in for an EventFieldMapping row - resolve() only ever reads these
    attributes."""

    source_path: str
    target_type: str = "custom_field"
    target_field: Optional[str] = None
    is_identity_key: bool = False
    _field_name: Optional[str] = None

    @property
    def field_name(self) -> Optional[str]:
        return self._field_name


def _custom_field_mapping(source_path: str, field_name: str) -> FakeMapping:
    return FakeMapping(
        source_path=source_path, target_type="custom_field", _field_name=field_name
    )


def _contact_field_mapping(
    source_path: str, target_field: str, is_identity_key: bool = False
) -> FakeMapping:
    return FakeMapping(
        source_path=source_path,
        target_type="contact_field",
        target_field=target_field,
        is_identity_key=is_identity_key,
    )


def test_contact_field_mapping_resolves_into_contact_field_values():
    mapping = _contact_field_mapping("person.first_name", "first_name")
    event_data = {"person": {"first_name": "Harry"}}

    result = resolve([mapping], event_data)

    assert result.contact_field_values == {"first_name": "Harry"}
    assert result.custom_field_values == {}
    assert result.has_identity is False


def test_custom_field_mapping_resolves_into_custom_field_values():
    mapping = _custom_field_mapping(
        "person.account.family_member_count", "family_member_count"
    )
    event_data = {"person": {"account": {"family_member_count": 3}}}

    result = resolve([mapping], event_data)

    assert result.custom_field_values == {"family_member_count": 3}
    assert result.contact_field_values == {}


def test_identity_key_mapping_sets_identity_not_contact_field_values():
    mapping = _contact_field_mapping("person.id", "external_id", is_identity_key=True)
    event_data = {"person": {"id": "abc-123"}}

    result = resolve([mapping], event_data)

    assert result.identity_field == "external_id"
    assert result.identity_value == "abc-123"
    assert result.has_identity is True
    assert result.contact_field_values == {}


def test_missing_path_is_skipped_not_an_error():
    mapping = _custom_field_mapping("person.does.not.exist", "some_field")

    result = resolve([mapping], {"person": {}})

    assert result.custom_field_values == {}


def test_identity_key_missing_path_leaves_no_identity():
    mapping = _contact_field_mapping("person.id", "external_id", is_identity_key=True)

    result = resolve([mapping], {"person": {}})

    assert result.has_identity is False
    assert result.identity_field is None
    assert result.identity_value is None


def test_no_identity_key_mapping_present_leaves_no_identity():
    mapping = _custom_field_mapping("person.name", "some_field")

    result = resolve([mapping], {"person": {"name": "Harry"}})

    assert result.has_identity is False


def test_multiple_mixed_mappings_all_resolve_independently():
    mappings = [
        _contact_field_mapping("person.id", "external_id", is_identity_key=True),
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

    result = resolve(mappings, event_data)

    assert result.identity_field == "external_id"
    assert result.identity_value == "abc-123"
    assert result.contact_field_values == {"first_name": "Harry"}
    assert result.custom_field_values == {"family_member_count": 3}


def test_no_mappings_returns_empty_result():
    result = resolve([], {"person": {"id": "abc-123"}})

    assert result.has_identity is False
    assert result.contact_field_values == {}
    assert result.custom_field_values == {}

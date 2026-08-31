import pytest

from app.repositories.contact_custom_field_value_repository import (
    ContactCustomFieldValueRepository,
    CustomFieldValueTypeError,
    UndefinedCustomFieldError,
)


def test_first_write_creates_value(
    db, test_contact, test_custom_field_definition, test_user
):
    repository = ContactCustomFieldValueRepository(db)
    value = repository.set_value(
        contact_id=test_contact.id,
        field_name=test_custom_field_definition.name,
        value="hello",
        set_by_user_id=test_user.id,
    )

    assert value.id is not None
    assert value.value == "hello"
    assert value.set_by_user_id == test_user.id
    assert value.field_definition_id == test_custom_field_definition.id


def test_second_write_overwrites_not_appends(
    db, test_contact, test_custom_field_definition, test_user
):
    repository = ContactCustomFieldValueRepository(db)
    first = repository.set_value(
        contact_id=test_contact.id,
        field_name=test_custom_field_definition.name,
        value="hello",
        set_by_user_id=test_user.id,
    )
    second = repository.set_value(
        contact_id=test_contact.id,
        field_name=test_custom_field_definition.name,
        value="goodbye",
        set_by_user_id=test_user.id,
    )

    assert second.id == first.id
    assert second.value == "goodbye"
    assert len(repository.list_values_for_contact(test_contact.id)) == 1


def test_write_mismatched_type_rejected(
    db, test_contact, test_custom_field_definition, test_user
):
    """test_custom_field_definition is STRING - a number must be rejected."""
    repository = ContactCustomFieldValueRepository(db)
    with pytest.raises(CustomFieldValueTypeError):
        repository.set_value(
            contact_id=test_contact.id,
            field_name=test_custom_field_definition.name,
            value=3,
            set_by_user_id=test_user.id,
        )

    assert repository.list_values_for_contact(test_contact.id) == []


def test_write_number_field_accepts_number(
    db, test_contact, test_number_field_definition, test_user
):
    repository = ContactCustomFieldValueRepository(db)
    value = repository.set_value(
        contact_id=test_contact.id,
        field_name=test_number_field_definition.name,
        value=3,
        set_by_user_id=test_user.id,
    )
    assert value.value == 3


def test_write_number_field_rejects_bool(
    db, test_contact, test_number_field_definition, test_user
):
    """bool is a subclass of int in Python - must not silently pass as NUMBER."""
    repository = ContactCustomFieldValueRepository(db)
    with pytest.raises(CustomFieldValueTypeError):
        repository.set_value(
            contact_id=test_contact.id,
            field_name=test_number_field_definition.name,
            value=True,
            set_by_user_id=test_user.id,
        )


def test_write_undefined_field_rejected(db, test_contact, test_user):
    repository = ContactCustomFieldValueRepository(db)
    with pytest.raises(UndefinedCustomFieldError):
        repository.set_value(
            contact_id=test_contact.id,
            field_name="does_not_exist",
            value="hello",
            set_by_user_id=test_user.id,
        )


def test_set_by_user_id_recorded_and_updated_on_overwrite(
    db, test_contact, test_custom_field_definition, test_user, setup_user
):
    repository = ContactCustomFieldValueRepository(db)
    first = repository.set_value(
        contact_id=test_contact.id,
        field_name=test_custom_field_definition.name,
        value="hello",
        set_by_user_id=test_user.id,
    )
    assert first.set_by_user_id == test_user.id

    second = repository.set_value(
        contact_id=test_contact.id,
        field_name=test_custom_field_definition.name,
        value="world",
        set_by_user_id=setup_user.id,
    )
    assert second.set_by_user_id == setup_user.id


def test_delete_value(db, test_contact, test_custom_field_definition, test_user):
    repository = ContactCustomFieldValueRepository(db)
    repository.set_value(
        contact_id=test_contact.id,
        field_name=test_custom_field_definition.name,
        value="hello",
        set_by_user_id=test_user.id,
    )

    assert (
        repository.delete_value(test_contact.id, test_custom_field_definition.name)
        is True
    )
    assert repository.list_values_for_contact(test_contact.id) == []


def test_delete_value_not_found(db, test_contact, test_custom_field_definition):
    repository = ContactCustomFieldValueRepository(db)
    assert (
        repository.delete_value(test_contact.id, test_custom_field_definition.name)
        is False
    )

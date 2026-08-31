import pytest
from app.models.custom_field_definition import CustomFieldDefinition
from app.models.contact_custom_field_value import ContactCustomFieldValue


@pytest.fixture(scope="function")
def test_custom_field_definition(db, faker, test_user):
    """Create a STRING custom field definition for use in tests."""
    definition = CustomFieldDefinition(
        name=faker.unique.slug(),
        value_type="string",
        label="Test Field",
        created_by_id=test_user.id,
    )
    db.add(definition)
    db.commit()
    db.refresh(definition)

    return definition


@pytest.fixture(scope="function")
def test_number_field_definition(db, faker, test_user):
    """Create a NUMBER custom field definition for use in tests."""
    definition = CustomFieldDefinition(
        name=faker.unique.slug(),
        value_type="number",
        created_by_id=test_user.id,
    )
    db.add(definition)
    db.commit()
    db.refresh(definition)

    return definition


@pytest.fixture(scope="function")
def test_contact_custom_field_value(
    db, test_contact, test_custom_field_definition, test_user
):
    """Create a custom field value for test_contact against test_custom_field_definition."""
    value = ContactCustomFieldValue(
        contact_id=test_contact.id,
        field_definition_id=test_custom_field_definition.id,
        value="hello",
        set_by_user_id=test_user.id,
    )
    db.add(value)
    db.commit()
    db.refresh(value)

    return value

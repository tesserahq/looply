import pytest

from app.repositories.custom_field_definition_repository import (
    CustomFieldDefinitionNameConflictError,
    CustomFieldDefinitionRepository,
)
from app.schemas.custom_field_definition import (
    CustomFieldDefinitionCreate,
    FieldValueType,
)


def test_create_definition(db, faker, test_user):
    repository = CustomFieldDefinitionRepository(db)
    name = faker.unique.slug()
    definition = repository.create_definition(
        CustomFieldDefinitionCreate(
            name=name,
            value_type=FieldValueType.STRING,
            label="Label",
            created_by_id=test_user.id,
        )
    )

    assert definition.id is not None
    assert definition.name == name
    assert definition.value_type == "string"
    assert definition.created_by_id == test_user.id


def test_create_definition_host_call_has_no_created_by(db, faker):
    """created_by_id is null when created by a host API call, not through the UI."""
    repository = CustomFieldDefinitionRepository(db)
    definition = repository.create_definition(
        CustomFieldDefinitionCreate(
            name=faker.unique.slug(),
            value_type=FieldValueType.NUMBER,
        )
    )

    assert definition.created_by_id is None


def test_create_definition_duplicate_name_conflict(db, faker, test_user):
    repository = CustomFieldDefinitionRepository(db)
    name = faker.unique.slug()
    repository.create_definition(
        CustomFieldDefinitionCreate(
            name=name, value_type=FieldValueType.STRING, created_by_id=test_user.id
        )
    )

    with pytest.raises(CustomFieldDefinitionNameConflictError):
        repository.create_definition(
            CustomFieldDefinitionCreate(
                name=name.upper(),  # case-insensitive collision
                value_type=FieldValueType.NUMBER,
                created_by_id=test_user.id,
            )
        )


def test_delete_and_recreate_same_name(db, faker, test_user):
    """The PRD's stated fix for a typo'd name or wrong value_type: soft-delete then
    recreate with the same name must succeed, not hit the old row's unique index."""
    repository = CustomFieldDefinitionRepository(db)
    name = faker.unique.slug()
    original = repository.create_definition(
        CustomFieldDefinitionCreate(
            name=name, value_type=FieldValueType.STRING, created_by_id=test_user.id
        )
    )

    assert repository.delete_definition(original.id) is True

    recreated = repository.create_definition(
        CustomFieldDefinitionCreate(
            name=name, value_type=FieldValueType.NUMBER, created_by_id=test_user.id
        )
    )

    assert recreated.id != original.id
    assert recreated.value_type == "number"


def test_soft_deleted_definition_not_returned_by_get_or_list(db, faker, test_user):
    repository = CustomFieldDefinitionRepository(db)
    definition = repository.create_definition(
        CustomFieldDefinitionCreate(
            name=faker.unique.slug(),
            value_type=FieldValueType.STRING,
            created_by_id=test_user.id,
        )
    )
    repository.delete_definition(definition.id)

    assert repository.get_definition(definition.id) is None
    assert repository.get_definition_by_name(definition.name) is None
    assert definition.id not in [d.id for d in repository.get_definitions_query().all()]


def test_get_definition_by_name_case_insensitive(db, faker, test_user):
    repository = CustomFieldDefinitionRepository(db)
    definition = repository.create_definition(
        CustomFieldDefinitionCreate(
            name="Family_Member_Count",
            value_type=FieldValueType.NUMBER,
            created_by_id=test_user.id,
        )
    )

    found = repository.get_definition_by_name("family_member_count")
    assert found is not None
    assert found.id == definition.id

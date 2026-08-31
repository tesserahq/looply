from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate

from app.db import get_db
from app.models.contact import Contact
from app.schemas.custom_field_definition import (
    CustomFieldDefinition,
    CustomFieldDefinitionCreate,
    CustomFieldDefinitionCreateRequest,
)
from app.schemas.contact_custom_field_value import (
    ContactCustomFieldValue,
    ContactCustomFieldValueWrite,
)
from app.repositories.custom_field_definition_repository import (
    CustomFieldDefinitionNameConflictError,
    CustomFieldDefinitionRepository,
)
from app.repositories.contact_custom_field_value_repository import (
    ContactCustomFieldValueRepository,
    CustomFieldValueTypeError,
    UndefinedCustomFieldError,
)
from app.routers.utils.dependencies import get_contact_by_external_id
from app.schemas.user import User
from tessera_sdk.server.dependencies.auth import get_current_user
from app.auth.rbac import build_rbac_dependencies

router = APIRouter(
    prefix="/custom-field-definitions",
    tags=["custom-fields"],
    responses={404: {"description": "Not found"}},
)

# Nested under /contacts/{external_id} - the host already knows its own account/user
# id and shouldn't need to look up Looply's internal contact UUID first (user story 7).
nested_router = APIRouter(
    prefix="/contacts/{external_id}/custom-fields",
    tags=["custom-fields"],
    responses={404: {"description": "Not found"}},
)

RESOURCE = "custom_field"
rbac = build_rbac_dependencies(resource=RESOURCE)


@router.post(
    "", response_model=CustomFieldDefinition, status_code=status.HTTP_201_CREATED
)
def create_custom_field_definition(
    definition_data: CustomFieldDefinitionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _authorized: bool = Depends(rbac["create"]),
):
    """Create a new custom field definition. name and value_type are immutable
    once set - see docs/prds/0002-contact-custom-fields-and-events.md."""
    definition = CustomFieldDefinitionCreate(
        **definition_data.model_dump(),
        created_by_id=current_user.id,
    )
    try:
        return CustomFieldDefinitionRepository(db).create_definition(definition)
    except CustomFieldDefinitionNameConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("", response_model=Page[CustomFieldDefinition])
def list_custom_field_definitions(
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["read"]),
):
    """List all active custom field definitions with pagination."""
    return paginate(db, CustomFieldDefinitionRepository(db).get_definitions_query())


@router.delete("/{definition_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_custom_field_definition(
    definition_id: UUID,
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["delete"]),
):
    """Soft delete a custom field definition. Its values stop appearing in a
    contact's field list without a separate cleanup step."""
    if not CustomFieldDefinitionRepository(db).delete_definition(definition_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom field definition not found",
        )


@nested_router.put("/{field_name}", response_model=ContactCustomFieldValue)
def set_contact_custom_field_value(
    field_name: str,
    value_data: ContactCustomFieldValueWrite,
    contact: Contact = Depends(get_contact_by_external_id),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _authorized: bool = Depends(rbac["update"]),
):
    """Upsert a contact's value for a named field - one call for both a host
    integration (API key) and an operator manual correction (Looply UI), since the
    only real difference between them is who is calling."""
    try:
        return ContactCustomFieldValueRepository(db).set_value(
            contact_id=contact.id,
            field_name=field_name,
            value=value_data.value,
            set_by_user_id=current_user.id,
        )
    except UndefinedCustomFieldError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)
        )
    except CustomFieldValueTypeError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)
        )


@nested_router.get("", response_model=list[ContactCustomFieldValue])
def list_contact_custom_field_values(
    contact: Contact = Depends(get_contact_by_external_id),
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["read"]),
):
    """List a contact's current custom field values."""
    return ContactCustomFieldValueRepository(db).list_values_for_contact(contact.id)


@nested_router.delete("/{field_name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact_custom_field_value(
    field_name: str,
    contact: Contact = Depends(get_contact_by_external_id),
    db: Session = Depends(get_db),
    _authorized: bool = Depends(rbac["delete"]),
):
    """Delete a contact's value for a named field - a manual correction, distinct
    from deleting the field definition itself."""
    if not ContactCustomFieldValueRepository(db).delete_value(contact.id, field_name):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No value set for field {field_name!r} on this contact",
        )

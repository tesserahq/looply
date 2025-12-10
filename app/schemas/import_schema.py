from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime


class ImportBase(BaseModel):
    """Base import model containing common import attributes."""

    settings: dict
    """JSON field containing import settings (e.g., file_name and other metadata)."""

    processed_contacts: int = 0
    """Number of contacts successfully processed during the import."""

    failed_contacts: int = 0
    """Number of contacts that failed during the import."""

    user_id: UUID
    """ID of the user who performed the import."""


class ImportCreate(ImportBase):
    """Schema for creating a new import record."""

    pass


class ImportUpdate(BaseModel):
    """Schema for updating an existing import record. All fields are optional."""

    settings: Optional[dict] = None
    """Updated import settings."""

    processed_contacts: Optional[int] = None
    """Updated count of processed contacts."""

    failed_contacts: Optional[int] = None
    """Updated count of failed contacts."""


class ImportInDB(ImportBase):
    """Schema representing an import as stored in the database."""

    id: UUID
    """Unique identifier for the import in the database."""

    created_at: datetime
    """Timestamp when the import record was created."""

    updated_at: datetime
    """Timestamp when the import record was last updated."""

    model_config = {"from_attributes": True}


class Import(ImportInDB):
    """Schema for import data returned in API responses."""

    pass


class BatchContactImportRequest(BaseModel):
    """Schema for batch contact import requests with settings."""

    contacts: list
    """List of contacts to import."""

    settings: dict
    """Import settings including file_name and other metadata."""

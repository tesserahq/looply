from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.contact import Contact
from app.schemas.contact import ContactCreate, ContactUpdate
from app.services.soft_delete_service import SoftDeleteService
from app.utils.db.filtering import apply_filters


class ContactService(SoftDeleteService[Contact]):
    """Service class for managing contact CRUD operations."""

    def __init__(self, db: Session):
        """
        Initialize the contact service.

        Args:
            db: Database session
        """
        super().__init__(db, Contact)

    def get_contact(self, contact_id: UUID) -> Optional[Contact]:
        """
        Get a single contact by ID.

        Args:
            contact_id: The ID of the contact to retrieve

        Returns:
            Optional[Contact]: The contact or None if not found
        """
        return self.db.query(Contact).filter(Contact.id == contact_id).first()

    def get_contact_by_email(self, email: str) -> Optional[Contact]:
        """
        Get a contact by email address.

        Args:
            email: The email address of the contact to retrieve

        Returns:
            Optional[Contact]: The contact or None if not found
        """
        return self.db.query(Contact).filter(Contact.email == email).first()

    def get_contact_by_phone(self, phone: str) -> Optional[Contact]:
        """
        Get a contact by phone number.

        Args:
            phone: The phone number of the contact to retrieve

        Returns:
            Optional[Contact]: The contact or None if not found
        """
        return self.db.query(Contact).filter(Contact.phone == phone).first()

    def get_contacts(self, skip: int = 0, limit: int = 100) -> List[Contact]:
        """
        Get a list of contacts with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List[Contact]: List of contacts
        """
        return self.db.query(Contact).offset(skip).limit(limit).all()

    def get_contacts_query(self):
        """
        Get a query for all contacts.
        This is useful for pagination with fastapi-pagination.

        Returns:
            Query: SQLAlchemy query object for contacts
        """
        return self.db.query(Contact).order_by(Contact.created_at.desc())

    def get_contacts_by_creator(
        self, created_by_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[Contact]:
        """
        Get all contacts created by a specific user.

        Args:
            created_by_id: The ID of the user who created the contacts
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List[Contact]: List of contacts created by the user
        """
        return (
            self.db.query(Contact)
            .filter(Contact.created_by_id == created_by_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_active_contacts(self, skip: int = 0, limit: int = 100) -> List[Contact]:
        """
        Get all active contacts.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List[Contact]: List of active contacts
        """
        return (
            self.db.query(Contact)
            .filter(Contact.is_active == True)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create_contact(self, contact: ContactCreate) -> Contact:
        """
        Create a new contact.

        Args:
            contact: The contact data to create

        Returns:
            Contact: The created contact
        """
        db_contact = Contact(**contact.model_dump())
        self.db.add(db_contact)
        self.db.commit()
        self.db.refresh(db_contact)
        return db_contact

    def update_contact(
        self, contact_id: UUID, contact: ContactUpdate
    ) -> Optional[Contact]:
        """
        Update an existing contact.

        Args:
            contact_id: The ID of the contact to update
            contact: The updated contact data

        Returns:
            Optional[Contact]: The updated contact or None if not found
        """
        db_contact = self.db.query(Contact).filter(Contact.id == contact_id).first()
        if db_contact:
            update_data = contact.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(db_contact, key, value)
            self.db.commit()
            self.db.refresh(db_contact)
        return db_contact

    def delete_contact(self, contact_id: UUID) -> bool:
        """
        Soft delete a contact.

        Args:
            contact_id: The ID of the contact to delete

        Returns:
            bool: True if the contact was deleted, False otherwise
        """
        return self.delete_record(contact_id)

    def search(self, filters: dict) -> List[Contact]:
        """
        Search contacts based on dynamic filter criteria.

        Args:
            filters: A dictionary where keys are field names and values are either:
                - A direct value (e.g. {"first_name": "John"})
                - A dictionary with 'operator' and 'value' keys (e.g. {"first_name": {"operator": "ilike", "value": "%john%"}})

        Returns:
            List[Contact]: Filtered list of contacts matching the criteria.
        """
        query = self.db.query(Contact)
        query = apply_filters(query, Contact, filters)
        return query.all()

    def search_by_full_text(self, search_term: str) -> List[Contact]:
        """
        Search contacts using PostgreSQL full-text search.

        Args:
            search_term: The term to search for

        Returns:
            List[Contact]: List of contacts matching the search term
        """
        return self.db.query(Contact).filter(Contact.fts.match(search_term)).all()

    def restore_contact(self, contact_id: UUID) -> bool:
        """Restore a soft-deleted contact by setting deleted_at to None."""
        return self.restore_record(contact_id)

    def hard_delete_contact(self, contact_id: UUID) -> bool:
        """Permanently delete a contact from the database."""
        return self.hard_delete_record(contact_id)

    def get_deleted_contacts(self, skip: int = 0, limit: int = 100) -> List[Contact]:
        """Get all soft-deleted contacts."""
        return self.get_deleted_records(skip, limit)

    def get_deleted_contact(self, contact_id: UUID) -> Optional[Contact]:
        """Get a single soft-deleted contact by ID."""
        return self.get_deleted_record(contact_id)

    def get_contacts_deleted_after(self, date) -> List[Contact]:
        """Get contacts deleted after a specific date."""
        return self.get_records_deleted_after(date)

    def toggle_contact_active_status(self, contact_id: UUID) -> Optional[Contact]:
        """
        Toggle the active status of a contact.

        Args:
            contact_id: The ID of the contact to toggle

        Returns:
            Optional[Contact]: The updated contact or None if not found
        """
        db_contact = self.db.query(Contact).filter(Contact.id == contact_id).first()
        if db_contact:
            db_contact.is_active = not db_contact.is_active
            self.db.commit()
            self.db.refresh(db_contact)
        return db_contact

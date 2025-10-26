from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.contact_list import ContactList
from app.schemas.contact_list import ContactListCreate, ContactListUpdate
from app.services.soft_delete_service import SoftDeleteService
from app.utils.db.filtering import apply_filters


class ContactListService(SoftDeleteService[ContactList]):
    """Service class for managing contact list CRUD operations."""

    def __init__(self, db: Session):
        """
        Initialize the contact list service.

        Args:
            db: Database session
        """
        super().__init__(db, ContactList)

    def get_contact_list(self, contact_list_id: UUID) -> Optional[ContactList]:
        """
        Get a single contact list by ID.

        Args:
            contact_list_id: The ID of the contact list to retrieve

        Returns:
            Optional[ContactList]: The contact list or None if not found
        """
        return (
            self.db.query(ContactList).filter(ContactList.id == contact_list_id).first()
        )

    def get_contact_lists(self, skip: int = 0, limit: int = 100) -> List[ContactList]:
        """
        Get a list of contact lists with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List[ContactList]: List of contact lists
        """
        return self.db.query(ContactList).offset(skip).limit(limit).all()

    def get_contact_lists_query(self):
        """
        Get a query for all contact lists.
        This is useful for pagination with fastapi-pagination.

        Returns:
            Query: SQLAlchemy query object for contact lists
        """
        return self.db.query(ContactList).order_by(ContactList.created_at.desc())

    def get_contact_lists_by_creator(
        self, created_by_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[ContactList]:
        """
        Get all contact lists created by a specific user.

        Args:
            created_by_id: The ID of the user who created the contact lists
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List[ContactList]: List of contact lists created by the user
        """
        return (
            self.db.query(ContactList)
            .filter(ContactList.created_by_id == created_by_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create_contact_list(self, contact_list: ContactListCreate) -> ContactList:
        """
        Create a new contact list.

        Args:
            contact_list: The contact list data to create

        Returns:
            ContactList: The created contact list
        """
        db_contact_list = ContactList(**contact_list.model_dump())
        self.db.add(db_contact_list)
        self.db.commit()
        self.db.refresh(db_contact_list)
        return db_contact_list

    def update_contact_list(
        self, contact_list_id: UUID, contact_list: ContactListUpdate
    ) -> Optional[ContactList]:
        """
        Update an existing contact list.

        Args:
            contact_list_id: The ID of the contact list to update
            contact_list: The updated contact list data

        Returns:
            Optional[ContactList]: The updated contact list or None if not found
        """
        db_contact_list = (
            self.db.query(ContactList).filter(ContactList.id == contact_list_id).first()
        )
        if db_contact_list:
            update_data = contact_list.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(db_contact_list, key, value)
            self.db.commit()
            self.db.refresh(db_contact_list)
        return db_contact_list

    def delete_contact_list(self, contact_list_id: UUID) -> bool:
        """
        Soft delete a contact list.

        Args:
            contact_list_id: The ID of the contact list to delete

        Returns:
            bool: True if the contact list was deleted, False otherwise
        """
        return self.delete_record(contact_list_id)

    def search(self, filters: dict) -> List[ContactList]:
        """
        Search contact lists based on dynamic filter criteria.

        Args:
            filters: A dictionary where keys are field names and values are either:
                - A direct value (e.g. {"name": "Marketing"})
                - A dictionary with 'operator' and 'value' keys (e.g. {"name": {"operator": "ilike", "value": "%marketing%"}})

        Returns:
            List[ContactList]: Filtered list of contact lists matching the criteria.
        """
        query = self.db.query(ContactList)
        query = apply_filters(query, ContactList, filters)
        return query.all()

    def restore_contact_list(self, contact_list_id: UUID) -> bool:
        """Restore a soft-deleted contact list by setting deleted_at to None."""
        return self.restore_record(contact_list_id)

    def hard_delete_contact_list(self, contact_list_id: UUID) -> bool:
        """Permanently delete a contact list from the database."""
        return self.hard_delete_record(contact_list_id)

    def get_deleted_contact_lists(
        self, skip: int = 0, limit: int = 100
    ) -> List[ContactList]:
        """Get all soft-deleted contact lists."""
        return self.get_deleted_records(skip, limit)

    def get_deleted_contact_list(self, contact_list_id: UUID) -> Optional[ContactList]:
        """Get a single soft-deleted contact list by ID."""
        return self.get_deleted_record(contact_list_id)

    def get_contact_lists_deleted_after(self, date) -> List[ContactList]:
        """Get contact lists deleted after a specific date."""
        return self.get_records_deleted_after(date)

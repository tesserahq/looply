from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.contact_list import ContactList
from app.models.contact_list_member import ContactListMember
from app.models.contact import Contact
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

    def get_public_contact_lists_query(self):
        """
        Get a query for all public contact lists.
        This is useful for pagination with fastapi-pagination.

        Returns:
            Query: SQLAlchemy query object for public contact lists
        """
        return (
            self.db.query(ContactList)
            .filter(ContactList.is_public == True)
            .order_by(ContactList.created_at.desc())
        )

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

    # Member management methods

    def add_contact_to_list(
        self, contact_list_id: UUID, contact_id: UUID
    ) -> Optional[ContactListMember]:
        """
        Add a contact to a contact list.

        Args:
            contact_list_id: The ID of the contact list
            contact_id: The ID of the contact to add

        Returns:
            Optional[ContactListMember]: The created membership or None if contact is already in list
        """
        # Check if contact list exists
        contact_list = self.get_contact_list(contact_list_id)
        if not contact_list:
            return None

        # Check if contact exists
        contact = self.db.query(Contact).filter(Contact.id == contact_id).first()
        if not contact:
            return None

        # Check if member already exists
        existing_member = (
            self.db.query(ContactListMember)
            .filter(
                ContactListMember.contact_list_id == contact_list_id,
                ContactListMember.contact_id == contact_id,
            )
            .first()
        )

        if existing_member:
            return None

        # Create new membership
        member = ContactListMember(
            contact_list_id=contact_list_id, contact_id=contact_id
        )
        self.db.add(member)
        self.db.commit()
        self.db.refresh(member)
        return member

    def remove_contact_from_list(self, contact_list_id: UUID, contact_id: UUID) -> bool:
        """
        Remove a contact from a contact list (soft delete).

        Args:
            contact_list_id: The ID of the contact list
            contact_id: The ID of the contact to remove

        Returns:
            bool: True if the contact was removed, False otherwise
        """
        member = (
            self.db.query(ContactListMember)
            .filter(
                ContactListMember.contact_list_id == contact_list_id,
                ContactListMember.contact_id == contact_id,
            )
            .first()
        )

        if not member:
            return False

        from datetime import datetime, timezone

        member.deleted_at = datetime.now(timezone.utc)
        self.db.commit()
        return True

    def get_list_members(self, contact_list_id: UUID) -> List[Contact]:
        """
        Get all active members (contacts) in a contact list.

        Args:
            contact_list_id: The ID of the contact list

        Returns:
            List[Contact]: List of contacts that are members of the list
        """
        return (
            self.db.query(Contact)
            .join(ContactListMember, Contact.id == ContactListMember.contact_id)
            .filter(ContactListMember.contact_list_id == contact_list_id)
            .filter(ContactListMember.deleted_at.is_(None))
            .all()
        )

    def get_contact_lists_for_contact(self, contact_id: UUID) -> List[ContactList]:
        """
        Get all contact lists that a contact belongs to.

        Args:
            contact_id: The ID of the contact

        Returns:
            List[ContactList]: List of contact lists the contact belongs to
        """
        return (
            self.db.query(ContactList)
            .join(
                ContactListMember, ContactList.id == ContactListMember.contact_list_id
            )
            .filter(ContactListMember.contact_id == contact_id)
            .filter(ContactListMember.deleted_at.is_(None))
            .all()
        )

    def is_contact_in_list(self, contact_list_id: UUID, contact_id: UUID) -> bool:
        """
        Check if a contact is a member of a contact list.

        Args:
            contact_list_id: The ID of the contact list
            contact_id: The ID of the contact

        Returns:
            bool: True if contact is in the list, False otherwise
        """
        member = (
            self.db.query(ContactListMember)
            .filter(
                ContactListMember.contact_list_id == contact_list_id,
                ContactListMember.contact_id == contact_id,
                ContactListMember.deleted_at.is_(None),
            )
            .first()
        )
        return member is not None

    def get_list_member_count(self, contact_list_id: UUID) -> int:
        """
        Get the count of active members in a contact list.

        Args:
            contact_list_id: The ID of the contact list

        Returns:
            int: Number of active members in the list
        """
        return (
            self.db.query(ContactListMember)
            .filter(ContactListMember.contact_list_id == contact_list_id)
            .filter(ContactListMember.deleted_at.is_(None))
            .count()
        )

    def add_contacts_to_list(
        self, contact_list_id: UUID, contact_ids: List[UUID]
    ) -> int:
        """
        Add multiple contacts to a contact list.

        Args:
            contact_list_id: The ID of the contact list
            contact_ids: List of contact IDs to add

        Returns:
            int: Number of contacts successfully added
        """
        added_count = 0
        for contact_id in contact_ids:
            member = self.add_contact_to_list(contact_list_id, contact_id)
            if member:
                added_count += 1
        return added_count

    def remove_contacts_from_list(
        self, contact_list_id: UUID, contact_ids: List[UUID]
    ) -> int:
        """
        Remove multiple contacts from a contact list.

        Args:
            contact_list_id: The ID of the contact list
            contact_ids: List of contact IDs to remove

        Returns:
            int: Number of contacts successfully removed
        """
        removed_count = 0
        for contact_id in contact_ids:
            if self.remove_contact_from_list(contact_list_id, contact_id):
                removed_count += 1
        return removed_count

    def clear_list_members(self, contact_list_id: UUID) -> int:
        """
        Remove all contacts from a contact list (soft delete all members).

        Args:
            contact_list_id: The ID of the contact list

        Returns:
            int: Number of contacts removed
        """
        from datetime import datetime, timezone

        members = (
            self.db.query(ContactListMember)
            .filter(
                ContactListMember.contact_list_id == contact_list_id,
                ContactListMember.deleted_at.is_(None),
            )
            .all()
        )

        count = len(members)
        now = datetime.now(timezone.utc)

        for member in members:
            member.deleted_at = now

        self.db.commit()
        return count

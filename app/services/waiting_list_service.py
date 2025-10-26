from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.waiting_list import WaitingList
from app.models.waiting_list_member import WaitingListMember
from app.models.contact import Contact
from app.schemas.waiting_list import WaitingListCreate, WaitingListUpdate
from app.services.soft_delete_service import SoftDeleteService
from app.utils.db.filtering import apply_filters
from app.constants.waiting_list import WaitingListMemberStatus


class WaitingListService(SoftDeleteService[WaitingList]):
    """Service class for managing waiting list CRUD operations."""

    def __init__(self, db: Session):
        """
        Initialize the waiting list service.

        Args:
            db: Database session
        """
        super().__init__(db, WaitingList)

    def get_waiting_list(self, waiting_list_id: UUID) -> Optional[WaitingList]:
        """
        Get a single waiting list by ID.

        Args:
            waiting_list_id: The ID of the waiting list to retrieve

        Returns:
            Optional[WaitingList]: The waiting list or None if not found
        """
        return (
            self.db.query(WaitingList).filter(WaitingList.id == waiting_list_id).first()
        )

    def get_waiting_lists(self, skip: int = 0, limit: int = 100) -> List[WaitingList]:
        """
        Get a list of waiting lists with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List[WaitingList]: List of waiting lists
        """
        return self.db.query(WaitingList).offset(skip).limit(limit).all()

    def get_waiting_lists_query(self):
        """
        Get a query for all waiting lists.
        This is useful for pagination with fastapi-pagination.

        Returns:
            Query: SQLAlchemy query object for waiting lists
        """
        return self.db.query(WaitingList).order_by(WaitingList.created_at.desc())

    def get_waiting_lists_by_creator(
        self, created_by_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[WaitingList]:
        """
        Get all waiting lists created by a specific user.

        Args:
            created_by_id: The ID of the user who created the waiting lists
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List[WaitingList]: List of waiting lists created by the user
        """
        return (
            self.db.query(WaitingList)
            .filter(WaitingList.created_by_id == created_by_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create_waiting_list(self, waiting_list: WaitingListCreate) -> WaitingList:
        """
        Create a new waiting list.

        Args:
            waiting_list: The waiting list data to create

        Returns:
            WaitingList: The created waiting list
        """
        db_waiting_list = WaitingList(**waiting_list.model_dump())
        self.db.add(db_waiting_list)
        self.db.commit()
        self.db.refresh(db_waiting_list)
        return db_waiting_list

    def update_waiting_list(
        self, waiting_list_id: UUID, waiting_list: WaitingListUpdate
    ) -> Optional[WaitingList]:
        """
        Update an existing waiting list.

        Args:
            waiting_list_id: The ID of the waiting list to update
            waiting_list: The updated waiting list data

        Returns:
            Optional[WaitingList]: The updated waiting list or None if not found
        """
        db_waiting_list = (
            self.db.query(WaitingList).filter(WaitingList.id == waiting_list_id).first()
        )
        if db_waiting_list:
            update_data = waiting_list.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(db_waiting_list, key, value)
            self.db.commit()
            self.db.refresh(db_waiting_list)
        return db_waiting_list

    def delete_waiting_list(self, waiting_list_id: UUID) -> bool:
        """
        Soft delete a waiting list.

        Args:
            waiting_list_id: The ID of the waiting list to delete

        Returns:
            bool: True if the waiting list was deleted, False otherwise
        """
        return self.delete_record(waiting_list_id)

    def search(self, filters: dict) -> List[WaitingList]:
        """
        Search waiting lists based on dynamic filter criteria.

        Args:
            filters: A dictionary where keys are field names and values are either:
                - A direct value (e.g. {"name": "Main List"})
                - A dictionary with 'operator' and 'value' keys (e.g. {"name": {"operator": "ilike", "value": "%main%"}})

        Returns:
            List[WaitingList]: Filtered list of waiting lists matching the criteria.
        """
        query = self.db.query(WaitingList)
        query = apply_filters(query, WaitingList, filters)
        return query.all()

    def restore_waiting_list(self, waiting_list_id: UUID) -> bool:
        """Restore a soft-deleted waiting list by setting deleted_at to None."""
        return self.restore_record(waiting_list_id)

    def hard_delete_waiting_list(self, waiting_list_id: UUID) -> bool:
        """Permanently delete a waiting list from the database."""
        return self.hard_delete_record(waiting_list_id)

    def get_deleted_waiting_lists(
        self, skip: int = 0, limit: int = 100
    ) -> List[WaitingList]:
        """Get all soft-deleted waiting lists."""
        return self.get_deleted_records(skip, limit)

    def get_deleted_waiting_list(self, waiting_list_id: UUID) -> Optional[WaitingList]:
        """Get a single soft-deleted waiting list by ID."""
        return self.get_deleted_record(waiting_list_id)

    def get_waiting_lists_deleted_after(self, date) -> List[WaitingList]:
        """Get waiting lists deleted after a specific date."""
        return self.get_records_deleted_after(date)

    # Member management methods

    def add_contact_to_list(
        self,
        waiting_list_id: UUID,
        contact_id: UUID,
        status: str = WaitingListMemberStatus.PENDING,
    ) -> Optional[WaitingListMember]:
        """
        Add a contact to a waiting list.

        Args:
            waiting_list_id: The ID of the waiting list
            contact_id: The ID of the contact to add
            status: The status of the member (default: "pending")

        Returns:
            Optional[WaitingListMember]: The created membership or None if contact is already in list
        """
        # Check if waiting list exists
        waiting_list = self.get_waiting_list(waiting_list_id)
        if not waiting_list:
            return None

        # Check if contact exists
        contact = self.db.query(Contact).filter(Contact.id == contact_id).first()
        if not contact:
            return None

        # Check if member already exists
        existing_member = (
            self.db.query(WaitingListMember)
            .filter(
                WaitingListMember.waiting_list_id == waiting_list_id,
                WaitingListMember.contact_id == contact_id,
            )
            .first()
        )

        if existing_member:
            return None

        # Create new membership
        member = WaitingListMember(
            waiting_list_id=waiting_list_id,
            contact_id=contact_id,
            status=status,
        )
        self.db.add(member)
        self.db.commit()
        self.db.refresh(member)
        return member

    def remove_contact_from_list(self, waiting_list_id: UUID, contact_id: UUID) -> bool:
        """
        Remove a contact from a waiting list (soft delete).

        Args:
            waiting_list_id: The ID of the waiting list
            contact_id: The ID of the contact to remove

        Returns:
            bool: True if the contact was removed, False otherwise
        """
        member = (
            self.db.query(WaitingListMember)
            .filter(
                WaitingListMember.waiting_list_id == waiting_list_id,
                WaitingListMember.contact_id == contact_id,
            )
            .first()
        )

        if not member:
            return False

        from datetime import datetime, timezone

        member.deleted_at = datetime.now(timezone.utc)
        self.db.commit()
        return True

    def update_member_status(
        self, waiting_list_id: UUID, contact_id: UUID, status: str
    ) -> Optional[WaitingListMember]:
        """
        Update the status of a member on a waiting list.

        Args:
            waiting_list_id: The ID of the waiting list
            contact_id: The ID of the contact
            status: The new status

        Returns:
            Optional[WaitingListMember]: The updated member or None if not found
        """
        member = (
            self.db.query(WaitingListMember)
            .filter(
                WaitingListMember.waiting_list_id == waiting_list_id,
                WaitingListMember.contact_id == contact_id,
            )
            .first()
        )

        if not member:
            return None

        member.status = status
        self.db.commit()
        self.db.refresh(member)
        return member

    def get_list_members(self, waiting_list_id: UUID) -> List[Contact]:
        """
        Get all active members (contacts) in a waiting list.

        Args:
            waiting_list_id: The ID of the waiting list

        Returns:
            List[Contact]: List of contacts that are members of the waiting list
        """
        return (
            self.db.query(Contact)
            .join(WaitingListMember, Contact.id == WaitingListMember.contact_id)
            .filter(WaitingListMember.waiting_list_id == waiting_list_id)
            .filter(WaitingListMember.deleted_at.is_(None))
            .all()
        )

    def get_waiting_lists_for_contact(self, contact_id: UUID) -> List[WaitingList]:
        """
        Get all waiting lists that a contact belongs to.

        Args:
            contact_id: The ID of the contact

        Returns:
            List[WaitingList]: List of waiting lists the contact belongs to
        """
        return (
            self.db.query(WaitingList)
            .join(
                WaitingListMember,
                WaitingList.id == WaitingListMember.waiting_list_id,
            )
            .filter(WaitingListMember.contact_id == contact_id)
            .filter(WaitingListMember.deleted_at.is_(None))
            .all()
        )

    def is_contact_in_list(self, waiting_list_id: UUID, contact_id: UUID) -> bool:
        """
        Check if a contact is a member of a waiting list.

        Args:
            waiting_list_id: The ID of the waiting list
            contact_id: The ID of the contact

        Returns:
            bool: True if contact is in the list, False otherwise
        """
        member = (
            self.db.query(WaitingListMember)
            .filter(
                WaitingListMember.waiting_list_id == waiting_list_id,
                WaitingListMember.contact_id == contact_id,
                WaitingListMember.deleted_at.is_(None),
            )
            .first()
        )
        return member is not None

    def get_list_member_count(self, waiting_list_id: UUID) -> int:
        """
        Get the count of active members in a waiting list.

        Args:
            waiting_list_id: The ID of the waiting list

        Returns:
            int: Number of active members in the list
        """
        return (
            self.db.query(WaitingListMember)
            .filter(WaitingListMember.waiting_list_id == waiting_list_id)
            .filter(WaitingListMember.deleted_at.is_(None))
            .count()
        )

    def add_contacts_to_list(
        self,
        waiting_list_id: UUID,
        contact_ids: List[UUID],
        status: str = WaitingListMemberStatus.PENDING,
    ) -> int:
        """
        Add multiple contacts to a waiting list.

        Args:
            waiting_list_id: The ID of the waiting list
            contact_ids: List of contact IDs to add
            status: The status for all added contacts (default: "pending")

        Returns:
            int: Number of contacts successfully added
        """
        added_count = 0
        for contact_id in contact_ids:
            member = self.add_contact_to_list(waiting_list_id, contact_id, status)
            if member:
                added_count += 1
        return added_count

    def remove_contacts_from_list(
        self, waiting_list_id: UUID, contact_ids: List[UUID]
    ) -> int:
        """
        Remove multiple contacts from a waiting list.

        Args:
            waiting_list_id: The ID of the waiting list
            contact_ids: List of contact IDs to remove

        Returns:
            int: Number of contacts successfully removed
        """
        removed_count = 0
        for contact_id in contact_ids:
            if self.remove_contact_from_list(waiting_list_id, contact_id):
                removed_count += 1
        return removed_count

    def clear_list_members(self, waiting_list_id: UUID) -> int:
        """
        Remove all contacts from a waiting list (soft delete all members).

        Args:
            waiting_list_id: The ID of the waiting list

        Returns:
            int: Number of contacts removed
        """
        from datetime import datetime, timezone

        members = (
            self.db.query(WaitingListMember)
            .filter(
                WaitingListMember.waiting_list_id == waiting_list_id,
                WaitingListMember.deleted_at.is_(None),
            )
            .all()
        )

        count = len(members)
        now = datetime.now(timezone.utc)

        for member in members:
            member.deleted_at = now

        self.db.commit()
        return count

    def get_members_by_status(
        self, waiting_list_id: UUID, status: str
    ) -> List[Contact]:
        """
        Get all members with a specific status on a waiting list.

        Args:
            waiting_list_id: The ID of the waiting list
            status: The status to filter by

        Returns:
            List[Contact]: List of contacts with the specified status
        """
        return (
            self.db.query(Contact)
            .join(WaitingListMember, Contact.id == WaitingListMember.contact_id)
            .filter(WaitingListMember.waiting_list_id == waiting_list_id)
            .filter(WaitingListMember.status == status)
            .filter(WaitingListMember.deleted_at.is_(None))
            .all()
        )

    def get_member_with_status(
        self, waiting_list_id: UUID, contact_id: UUID
    ) -> Optional[WaitingListMember]:
        """
        Get a member's record including their status.

        Args:
            waiting_list_id: The ID of the waiting list
            contact_id: The ID of the contact

        Returns:
            Optional[WaitingListMember]: The member record with status or None if not found
        """
        return (
            self.db.query(WaitingListMember)
            .filter(
                WaitingListMember.waiting_list_id == waiting_list_id,
                WaitingListMember.contact_id == contact_id,
                WaitingListMember.deleted_at.is_(None),
            )
            .first()
        )

    def get_member_count_by_status(self, waiting_list_id: UUID, status: str) -> int:
        """
        Get the count of members with a specific status.

        Args:
            waiting_list_id: The ID of the waiting list
            status: The status to filter by

        Returns:
            int: Number of members with the specified status
        """
        return (
            self.db.query(WaitingListMember)
            .filter(WaitingListMember.waiting_list_id == waiting_list_id)
            .filter(WaitingListMember.status == status)
            .filter(WaitingListMember.deleted_at.is_(None))
            .count()
        )

    def update_members_status_bulk(
        self, waiting_list_id: UUID, contact_ids: List[UUID], status: str
    ) -> int:
        """
        Update the status of multiple members at once.

        Args:
            waiting_list_id: The ID of the waiting list
            contact_ids: List of contact IDs to update
            status: The new status

        Returns:
            int: Number of members successfully updated
        """
        updated_count = 0
        for contact_id in contact_ids:
            member = self.update_member_status(waiting_list_id, contact_id, status)
            if member:
                updated_count += 1
        return updated_count

    def get_all_members_with_details(self, waiting_list_id: UUID) -> List[dict]:
        """
        Get all members with their full details including status.

        Args:
            waiting_list_id: The ID of the waiting list

        Returns:
            List[dict]: List of members with contact details and status
        """
        from app.schemas.contact import Contact as ContactSchema

        members = (
            self.db.query(WaitingListMember, Contact)
            .join(Contact, WaitingListMember.contact_id == Contact.id)
            .filter(WaitingListMember.waiting_list_id == waiting_list_id)
            .filter(WaitingListMember.deleted_at.is_(None))
            .all()
        )

        result = []
        for member, contact in members:
            contact_dict = ContactSchema.model_validate(contact).model_dump()
            result.append(
                {
                    "id": member.id,
                    "waiting_list_id": member.waiting_list_id,
                    "contact_id": member.contact_id,
                    "status": member.status,
                    "created_at": member.created_at,
                    "updated_at": member.updated_at,
                    "contact": contact_dict,
                }
            )

        return result

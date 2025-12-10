from typing import List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timezone, timedelta
from app.models.contact import Contact
from app.models.contact_list import ContactList
from app.models.contact_interaction import ContactInteraction


class StatsService:
    """Service class for retrieving statistics."""

    def __init__(self, db: Session):
        """
        Initialize the stats service.

        Args:
            db: Database session
        """
        self.db = db

    def get_number_of_contacts(self) -> int:
        """
        Get the total number of contacts (excluding soft-deleted).

        Returns:
            int: Number of contacts
        """
        return self.db.query(func.count(Contact.id)).scalar() or 0

    def get_number_of_lists(self) -> int:
        """
        Get the total number of contact lists (excluding soft-deleted).

        Returns:
            int: Number of contact lists
        """
        return self.db.query(func.count(ContactList.id)).scalar() or 0

    def get_number_of_public_lists(self) -> int:
        """
        Get the total number of public contact lists (excluding soft-deleted).

        Returns:
            int: Number of public contact lists
        """
        return (
            self.db.query(func.count(ContactList.id))
            .filter(ContactList.is_public == True)
            .scalar()
            or 0
        )

    def get_number_of_private_lists(self) -> int:
        """
        Get the total number of private contact lists (excluding soft-deleted).

        Returns:
            int: Number of private contact lists
        """
        return (
            self.db.query(func.count(ContactList.id))
            .filter(ContactList.is_public == False)
            .scalar()
            or 0
        )

    def get_upcoming_interactions(self) -> List[Tuple[ContactInteraction, Contact]]:
        """
        Get contact interactions with actions within the next 5 days, joined with contact information.

        Returns:
            List[Tuple[ContactInteraction, Contact]]: List of tuples containing interaction and contact
        """
        now = datetime.now(timezone.utc)
        five_days_from_now = now + timedelta(days=5)

        return (
            self.db.query(ContactInteraction, Contact)
            .join(Contact, ContactInteraction.contact_id == Contact.id)
            .filter(ContactInteraction.action.isnot(None))
            .filter(
                and_(
                    ContactInteraction.action_timestamp.isnot(None),
                    ContactInteraction.action_timestamp >= now,
                    ContactInteraction.action_timestamp <= five_days_from_now,
                )
            )
            .order_by(ContactInteraction.action_timestamp.asc())
            .all()
        )

    def get_last_contacts(self, limit: int = 5) -> List[Contact]:
        """
        Get the last N contacts created in the system (excluding soft-deleted).

        Args:
            limit: Maximum number of contacts to return (default: 5)

        Returns:
            List[Contact]: List of the most recently created contacts
        """
        return (
            self.db.query(Contact)
            .order_by(Contact.created_at.desc())
            .limit(limit)
            .all()
        )

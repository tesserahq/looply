from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.contact_interaction import ContactInteraction
from app.schemas.contact_interaction import (
    ContactInteractionCreate,
    ContactInteractionUpdate,
)
from app.services.soft_delete_service import SoftDeleteService
from app.utils.db.filtering import apply_filters


class ContactInteractionService(SoftDeleteService[ContactInteraction]):
    """Service class for managing contact interaction CRUD operations."""

    def __init__(self, db: Session):
        """
        Initialize the contact interaction service.

        Args:
            db: Database session
        """
        super().__init__(db, ContactInteraction)

    def get_contact_interaction(
        self, interaction_id: UUID
    ) -> Optional[ContactInteraction]:
        """
        Get a single contact interaction by ID.

        Args:
            interaction_id: The ID of the interaction to retrieve

        Returns:
            Optional[ContactInteraction]: The interaction or None if not found
        """
        return (
            self.db.query(ContactInteraction)
            .filter(ContactInteraction.id == interaction_id)
            .first()
        )

    def get_contact_interactions(
        self, skip: int = 0, limit: int = 100
    ) -> List[ContactInteraction]:
        """
        Get a list of contact interactions with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List[ContactInteraction]: List of interactions
        """
        return (
            self.db.query(ContactInteraction)
            .order_by(ContactInteraction.interaction_timestamp.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_contact_interactions_query(self):
        """
        Get a query for all contact interactions.
        This is useful for pagination with fastapi-pagination.

        Returns:
            Query: SQLAlchemy query object for interactions
        """
        return self.db.query(ContactInteraction).order_by(
            ContactInteraction.interaction_timestamp.desc()
        )

    def get_interactions_by_contact(
        self, contact_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[ContactInteraction]:
        """
        Get all interactions for a specific contact.

        Args:
            contact_id: The ID of the contact
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List[ContactInteraction]: List of interactions for the contact
        """
        return (
            self.db.query(ContactInteraction)
            .filter(ContactInteraction.contact_id == contact_id)
            .order_by(ContactInteraction.interaction_timestamp.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_interactions_by_contact_query(self, contact_id: UUID):
        """
        Get a query for all interactions for a specific contact.
        This is useful for pagination with fastapi-pagination.

        Args:
            contact_id: The ID of the contact

        Returns:
            Query: SQLAlchemy query object for interactions
        """
        return (
            self.db.query(ContactInteraction)
            .filter(ContactInteraction.contact_id == contact_id)
            .order_by(ContactInteraction.interaction_timestamp.desc())
        )

    def get_last_interaction(self, contact_id: UUID) -> Optional[ContactInteraction]:
        """
        Get the most recent interaction for a contact.

        Args:
            contact_id: The ID of the contact

        Returns:
            Optional[ContactInteraction]: The most recent interaction or None
        """
        return (
            self.db.query(ContactInteraction)
            .filter(ContactInteraction.contact_id == contact_id)
            .order_by(ContactInteraction.interaction_timestamp.desc())
            .first()
        )

    def get_pending_actions(
        self, skip: int = 0, limit: int = 100
    ) -> List[ContactInteraction]:
        """
        Get all interactions with pending actions (action_timestamp in the future or null with action set).

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List[ContactInteraction]: List of interactions with pending actions
        """
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        return (
            self.db.query(ContactInteraction)
            .filter(ContactInteraction.action.isnot(None))
            .filter(
                (ContactInteraction.action_timestamp.is_(None))
                | (ContactInteraction.action_timestamp > now)
            )
            .order_by(ContactInteraction.action_timestamp.asc().nullslast())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_pending_actions_query(self):
        """
        Get a query for all interactions with pending actions.
        This is useful for pagination with fastapi-pagination.

        Returns:
            Query: SQLAlchemy query object for pending actions
        """
        from datetime import datetime, timezone
        from sqlalchemy import or_

        now = datetime.now(timezone.utc)
        return (
            self.db.query(ContactInteraction)
            .filter(ContactInteraction.action.isnot(None))
            .filter(
                or_(
                    ContactInteraction.action_timestamp.is_(None),
                    ContactInteraction.action_timestamp > now,
                )
            )
            .order_by(ContactInteraction.action_timestamp.asc().nullslast())
        )

    def get_pending_actions_by_contact(
        self, contact_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[ContactInteraction]:
        """
        Get pending actions for a specific contact.

        Args:
            contact_id: The ID of the contact
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List[ContactInteraction]: List of interactions with pending actions for the contact
        """
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        return (
            self.db.query(ContactInteraction)
            .filter(ContactInteraction.contact_id == contact_id)
            .filter(ContactInteraction.action.isnot(None))
            .filter(
                (ContactInteraction.action_timestamp.is_(None))
                | (ContactInteraction.action_timestamp > now)
            )
            .order_by(ContactInteraction.action_timestamp.asc().nullslast())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create_contact_interaction(
        self, interaction: ContactInteractionCreate
    ) -> ContactInteraction:
        """
        Create a new contact interaction.

        Args:
            interaction: The interaction data to create

        Returns:
            ContactInteraction: The created interaction
        """
        db_interaction = ContactInteraction(**interaction.model_dump())
        self.db.add(db_interaction)
        self.db.commit()
        self.db.refresh(db_interaction)
        return db_interaction

    def update_contact_interaction(
        self, interaction_id: UUID, interaction: ContactInteractionUpdate
    ) -> Optional[ContactInteraction]:
        """
        Update an existing contact interaction.

        Args:
            interaction_id: The ID of the interaction to update
            interaction: The updated interaction data

        Returns:
            Optional[ContactInteraction]: The updated interaction or None if not found
        """
        db_interaction = (
            self.db.query(ContactInteraction)
            .filter(ContactInteraction.id == interaction_id)
            .first()
        )
        if db_interaction:
            update_data = interaction.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(db_interaction, key, value)
            self.db.commit()
            self.db.refresh(db_interaction)
        return db_interaction

    def delete_contact_interaction(self, interaction_id: UUID) -> bool:
        """
        Soft delete a contact interaction.

        Args:
            interaction_id: The ID of the interaction to delete

        Returns:
            bool: True if the interaction was deleted, False otherwise
        """
        return self.delete_record(interaction_id)

    def search(self, filters: dict) -> List[ContactInteraction]:
        """
        Search contact interactions based on dynamic filter criteria.

        Args:
            filters: A dictionary where keys are field names and values are either:
                - A direct value (e.g. {"contact_id": "..."})
                - A dictionary with 'operator' and 'value' keys

        Returns:
            List[ContactInteraction]: Filtered list of interactions matching the criteria.
        """
        query = self.db.query(ContactInteraction)
        query = apply_filters(query, ContactInteraction, filters)
        return query.all()

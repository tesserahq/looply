from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.contact import Contact
from app.schemas.contact import ContactCreate, ContactStatus, ContactType, ContactUpdate
from app.repositories.soft_delete_repository import SoftDeleteRepository
from app.repositories.tag_repository import TagRepository
from app.utils.db.filtering import apply_filters


class ContactRepository(SoftDeleteRepository[Contact]):
    """Repository class for managing contact CRUD operations."""

    def __init__(self, db: Session):
        """
        Initialize the contact repository.

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

    def get_contact_by_external_id(self, external_id: str) -> Optional[Contact]:
        """
        Get a contact by its external host platform identity.

        Args:
            external_id: The external id of the contact to retrieve

        Returns:
            Optional[Contact]: The contact or None if not found
        """
        return self.db.query(Contact).filter(Contact.external_id == external_id).first()

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

    def get_contacts_by_tags_query(self, tag_names: List[str]):
        """
        Get a query for active contacts having at least one of `tag_names`
        (case-insensitive, OR semantics), ordered newest-first for pagination.

        Args:
            tag_names: Tag names to filter by

        Returns:
            Query: SQLAlchemy query object for matching contacts
        """
        return (
            TagRepository(self.db)
            .get_contacts_by_tags_query(tag_names)
            .order_by(Contact.created_at.desc())
        )

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
            .filter(Contact.status == ContactStatus.ACTIVE.value)
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
        db_contact = Contact(**contact.model_dump(exclude={"tags"}))
        self.db.add(db_contact)
        self.db.commit()
        self.db.refresh(db_contact)
        if contact.tags:
            TagRepository(self.db).set_contact_tags(
                db_contact.id, contact.tags, contact.created_by_id
            )
            self.db.expire(db_contact, ["_tags_rel"])
        return db_contact

    def get_or_create_from_event(
        self,
        identity_field: str,
        identity_value: str,
        contact_field_values: dict,
        source: Optional[str],
        default_status: Optional[str] = None,
        default_tags: Optional[List[str]] = None,
    ) -> Contact:
        """
        Resolve an ingested NATS event to a Contact via identity_field
        ("external_id" or "email") and identity_value - the parent EventMapping's
        identity_target_field/identity_source_path for this event's event_type
        name both (see app.services.event_mapping_resolver and
        docs/prds/0003-event-driven-contact-resolution.md). Auto-creates one from
        contact_field_values if this identity hasn't been seen before.

        On a known identity, contact fields are never overwritten here - only
        Looply's own contact-edit flows do - so an event can't silently clobber
        data an operator has since corrected (see 0002's "Identity" and user
        story 10). default_status/default_tags (the parent EventMapping's
        configured defaults) are likewise only ever applied on the creation
        branch below, for the same reason - see
        docs/prds/0005-contact-status-and-event-mapping-defaults.md.

        A contact created this way has no authenticated Looply user
        (created_by_id=None) and no real phone/contact-type data from the event, so
        those get low-commitment placeholders an operator can correct later.

        A contact can predate this identity - created manually, or ingested
        before the source system attached this external_id - and only collide
        with the incoming event on email. When identity_field is
        "external_id" and no contact has that external_id yet, an email
        collision is checked for and, if found, that contact adopts the
        external_id instead of racing the unique email constraint on a
        duplicate insert.
        """
        existing = (
            self.get_contact_by_external_id(identity_value)
            if identity_field == "external_id"
            else self.get_contact_by_email(identity_value)
        )
        if not existing and identity_field == "external_id":
            email = contact_field_values.get("email")
            if email:
                existing = self.get_contact_by_email(email)
                if existing and not existing.external_id:
                    existing.external_id = identity_value
                    self.db.commit()
                    self.db.refresh(existing)
        if existing:
            return existing

        attrs = {**contact_field_values, identity_field: identity_value}
        if default_status:
            attrs["status"] = default_status
        contact = Contact(
            **attrs,
            contact_type=ContactType.LEAD.value,
            phone_type="",
            created_by_id=None,
            source=source,
        )
        self.db.add(contact)
        self.db.commit()
        self.db.refresh(contact)
        if default_tags:
            TagRepository(self.db).set_contact_tags(contact.id, default_tags, None)
            self.db.expire(contact, ["_tags_rel"])
        return contact

    def bulk_create_contacts(self, contacts: List[ContactCreate]) -> List[Contact]:
        """
        Bulk create multiple contacts in a single transaction.

        Args:
            contacts: List of contact data to create

        Returns:
            List[Contact]: List of created contacts
        """
        db_contacts = [
            Contact(**contact.model_dump(exclude={"tags"})) for contact in contacts
        ]
        self.db.add_all(db_contacts)
        self.db.flush()  # Flush to get IDs assigned
        self.db.commit()
        # Refresh all contacts to get full data including timestamps
        for contact in db_contacts:
            self.db.refresh(contact)
        return db_contacts

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
            tags = update_data.pop("tags", None)
            for key, value in update_data.items():
                setattr(db_contact, key, value)
            self.db.commit()
            if tags is not None:
                TagRepository(self.db).set_contact_tags(
                    contact_id, tags, db_contact.created_by_id
                )
            self.db.refresh(db_contact)
            if tags is not None:
                self.db.expire(db_contact, ["_tags_rel"])
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

    def search_text(
        self, search_term: str, skip: int = 0, limit: int = 100
    ) -> List[Contact]:
        """
        Search contacts by text using PostgreSQL full-text search (fts column).

        Args:
            search_term: The text to search for
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List[Contact]: List of contacts matching the search term
        """
        # Use plainto_tsquery to convert the search term to a proper tsquery
        # This handles plain text and converts it to a tsquery that PostgreSQL can understand
        tsquery = func.plainto_tsquery("simple_unaccent", search_term)
        return (
            self.db.query(Contact)
            .filter(Contact.fts.op("@@")(tsquery))
            .order_by(Contact.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_search_text_query(self, search_term: str):
        """
        Get a query for searching contacts by text using PostgreSQL full-text search.
        This is useful for pagination with fastapi-pagination.

        Args:
            search_term: The text to search for

        Returns:
            Query: SQLAlchemy query object for search results
        """
        tsquery = func.plainto_tsquery("simple_unaccent", search_term)
        return (
            self.db.query(Contact)
            .filter(Contact.fts.op("@@")(tsquery))
            .order_by(Contact.created_at.desc())
        )

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

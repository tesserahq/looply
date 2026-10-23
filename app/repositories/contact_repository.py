import re
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

    def list_contacts_query(
        self,
        q: Optional[str] = None,
        status: Optional[str] = None,
        contact_type: Optional[str] = None,
        tag_names: Optional[List[str]] = None,
    ):
        """
        Get a query for contacts filtered by any combination of full-text
        search (q), status, contact_type, and tags. All supplied filters are
        ANDed together; tags themselves are OR'd (at least one of
        `tag_names`, case-insensitive). Ordered newest-first, for pagination.
        This is the single query builder backing GET /contacts, unifying what
        used to be the separate GET /contacts/search endpoint.

        Args:
            q: Free-text search term, matched via PostgreSQL full-text search
            status: Exact ContactStatus value to filter by
            contact_type: Exact ContactType value to filter by
            tag_names: Tag names to filter by (OR semantics)

        Returns:
            Query: SQLAlchemy query object for matching contacts
        """
        query = (
            TagRepository(self.db).get_contacts_by_tags_query(tag_names)
            if tag_names
            else self.db.query(Contact)
        )

        if status:
            query = query.filter(Contact.status == status)
        if contact_type:
            query = query.filter(Contact.contact_type == contact_type)
        if q:
            tsquery = self._build_prefix_tsquery(q)
            query = query.filter(Contact.fts.op("@@")(tsquery))

        return query.order_by(Contact.created_at.desc())

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
        self.db.flush()
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
                    self.db.flush()
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
        self.db.flush()
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
            self.db.flush()
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

    def _build_prefix_tsquery(self, search_term: str):
        """
        Build a prefix-matching tsquery expression from free-text search input.

        Unlike plainto_tsquery, this matches each word as a *prefix*, so a
        partial term like "jane" matches both a word starting with "jane"
        (e.g. a first name "Jane") and a lexeme where "jane" is only a
        leading substring (e.g. the email "jane@hello.com", which Postgres'
        text search parser stores as a single "email" lexeme rather than
        splitting on "@"/"."). Falls back to plainto_tsquery if the input has
        no word characters (e.g. only punctuation).

        Args:
            search_term: The raw search text

        Returns:
            A SQLAlchemy function expression usable with the `@@` operator
        """
        # Split on whitespace only (not on punctuation) so multi-part tokens
        # like "jane@hello.com" stay intact for to_tsquery's own parser to
        # tokenize as a single email lexeme, matching how the fts column was
        # built. Strip tsquery-reserved operator characters to avoid syntax
        # errors from user input.
        sanitized = re.sub(r"[&|!():']", " ", search_term)
        words = sanitized.split()
        if not words:
            return func.plainto_tsquery("simple_unaccent", search_term)

        prefix_query = " & ".join(f"{word}:*" for word in words)
        return func.to_tsquery("simple_unaccent", prefix_query)

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
        tsquery = self._build_prefix_tsquery(search_term)
        return (
            self.db.query(Contact)
            .filter(Contact.fts.op("@@")(tsquery))
            .order_by(Contact.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
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

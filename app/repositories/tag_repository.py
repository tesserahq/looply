from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.tag import Tag
from app.models.contact_tag import ContactTag
from app.models.campaign_tag import CampaignTag
from app.repositories.soft_delete_repository import SoftDeleteRepository


class TagConflictError(ValueError):
    """Raised when a tag name collides with an existing active tag."""


class TagRepository(SoftDeleteRepository[Tag]):
    """Repository for the shared Tag entity and its contact/campaign
    assignments (contact_tags, campaign_tags).
    """

    def __init__(self, db: Session):
        super().__init__(db, Tag)

    # -- Tag CRUD --------------------------------------------------------

    def get_tag(self, tag_id: UUID) -> Optional[Tag]:
        """Get a single active tag by ID."""
        return self.db.query(Tag).filter(Tag.id == tag_id).first()

    def get_by_name(self, name: str) -> Optional[Tag]:
        """Get a single active tag by case-insensitive exact name match."""
        return (
            self.db.query(Tag)
            .filter(func.lower(Tag.name) == name.strip().lower())
            .first()
        )

    def get_tags_query(self):
        """Get a query for all active tags, for pagination."""
        return self.db.query(Tag).order_by(Tag.name)

    def get_tags_with_counts_query(self):
        """Query for all active tags plus their contact/campaign assignment
        counts, for the tags management list. Each row is a
        (Tag, contacts_count, campaigns_count) tuple - the counts are
        correlated scalar subqueries, so this is one query per page, not
        one per tag (no N+1)."""
        contacts_count = (
            select(func.count(ContactTag.id))
            .where(ContactTag.tag_id == Tag.id)
            .correlate(Tag)
            .scalar_subquery()
        )
        campaigns_count = (
            select(func.count(CampaignTag.id))
            .where(CampaignTag.tag_id == Tag.id)
            .correlate(Tag)
            .scalar_subquery()
        )
        return self.db.query(
            Tag,
            contacts_count.label("contacts_count"),
            campaigns_count.label("campaigns_count"),
        ).order_by(Tag.name)

    def get_usage_counts(self, tag_id: UUID) -> tuple[int, int]:
        """(contacts_count, campaigns_count) for a single tag - used by the
        delete-confirm usage check, where only one tag's counts are needed."""
        contacts_count = (
            self.db.query(func.count(ContactTag.id))
            .filter(ContactTag.tag_id == tag_id)
            .scalar()
        )
        campaigns_count = (
            self.db.query(func.count(CampaignTag.id))
            .filter(CampaignTag.tag_id == tag_id)
            .scalar()
        )
        return contacts_count, campaigns_count

    def create_tag(self, name: str, created_by_id: Optional[UUID]) -> Tag:
        """
        Create a new tag.

        Raises:
            TagConflictError: an active tag with this name (case-insensitive)
                already exists.
        """
        db_tag = Tag(name=name.strip(), created_by_id=created_by_id)
        self.db.add(db_tag)
        try:
            self.db.commit()
        except IntegrityError as e:
            self.db.rollback()
            raise TagConflictError(f"Tag {name!r} already exists") from e
        self.db.refresh(db_tag)
        return db_tag

    def update_tag(self, tag_id: UUID, name: str) -> Optional[Tag]:
        """
        Rename an existing tag.

        Raises:
            TagConflictError: another active tag already has this name
                (case-insensitive).
        """
        tag = self.get_tag(tag_id)
        if not tag:
            return None
        tag.name = name.strip()
        try:
            self.db.commit()
        except IntegrityError as e:
            self.db.rollback()
            raise TagConflictError(f"Tag {name!r} already exists") from e
        self.db.refresh(tag)
        return tag

    def delete_tag(self, tag_id: UUID) -> bool:
        """
        Soft delete a tag and remove it from every contact/campaign it's
        currently assigned to, in one transaction - a deleted tag never
        leaves a dangling reference behind.
        """
        tag = self.get_tag(tag_id)
        if not tag:
            return False
        self.db.query(ContactTag).filter(ContactTag.tag_id == tag_id).delete(
            synchronize_session=False
        )
        self.db.query(CampaignTag).filter(CampaignTag.tag_id == tag_id).delete(
            synchronize_session=False
        )
        tag.deleted_at = datetime.now(timezone.utc)
        self.db.commit()
        return True

    # -- Name-based resolution --------------------------------------------

    def get_or_create_tags(
        self, names: List[str], created_by_id: Optional[UUID]
    ) -> List[Tag]:
        """
        Resolve tag names to Tag rows, auto-creating any that don't exist yet
        as an active row. Deduplicated case-insensitively; blank names are
        skipped.

        A savepoint guards each creation attempt so a race with a concurrent
        request creating the same (case-insensitive) name can't abort the
        whole call - the loser just falls back to the winner's row instead
        of raising.
        """
        by_key: dict[str, Tag] = {}
        result: List[Tag] = []
        for raw in names:
            name = raw.strip()
            if not name:
                continue
            key = name.lower()
            tag = by_key.get(key)
            if tag is None:
                tag = self._get_or_create_one(name, key, created_by_id)
                by_key[key] = tag
            result.append(tag)
        return result

    def _get_or_create_one(
        self, name: str, key: str, created_by_id: Optional[UUID]
    ) -> Tag:
        existing = self.get_by_name(name)
        if existing:
            return existing
        try:
            with self.db.begin_nested():
                tag = Tag(name=name, created_by_id=created_by_id)
                self.db.add(tag)
                self.db.flush()
            return tag
        except IntegrityError:
            # Another concurrent request created this name first - use theirs.
            return self.get_by_name(name)

    # -- Contact assignment ------------------------------------------------

    def get_tags_for_contact(self, contact_id: UUID) -> List[Tag]:
        """Active tags currently assigned to a contact, alphabetically."""
        return (
            self.db.query(Tag)
            .join(ContactTag, ContactTag.tag_id == Tag.id)
            .filter(ContactTag.contact_id == contact_id)
            .order_by(Tag.name)
            .all()
        )

    def set_contact_tags(
        self, contact_id: UUID, tag_names: List[str], created_by_id: Optional[UUID]
    ) -> List[Tag]:
        """Replace a contact's full tag set with `tag_names` (auto-creating
        any that don't exist yet)."""
        tags = self.get_or_create_tags(tag_names, created_by_id)
        self.db.query(ContactTag).filter(ContactTag.contact_id == contact_id).delete(
            synchronize_session=False
        )
        self.db.add_all(
            [ContactTag(contact_id=contact_id, tag_id=tag.id) for tag in tags]
        )
        self.db.commit()
        return tags

    def get_contacts_by_tags_query(self, tag_names: List[str]):
        """Query for active contacts having at least one of `tag_names`
        (case-insensitive, OR semantics). Import-local to avoid a cycle with
        app.models.contact."""
        from app.models.contact import Contact

        normalized = [n.strip().lower() for n in tag_names if n.strip()]
        return (
            self.db.query(Contact)
            .join(ContactTag, ContactTag.contact_id == Contact.id)
            .join(Tag, Tag.id == ContactTag.tag_id)
            .filter(or_(*[func.lower(Tag.name) == n for n in normalized]))
            .distinct()
        )

    # -- Campaign assignment -------------------------------------------------

    def get_tags_for_campaign(self, campaign_id: UUID) -> List[Tag]:
        """Active tags currently assigned to a campaign, alphabetically."""
        return (
            self.db.query(Tag)
            .join(CampaignTag, CampaignTag.tag_id == Tag.id)
            .filter(CampaignTag.campaign_id == campaign_id)
            .order_by(Tag.name)
            .all()
        )

    def set_campaign_tags(
        self, campaign_id: UUID, tag_names: List[str], created_by_id: Optional[UUID]
    ) -> List[Tag]:
        """Replace a campaign's full tag set with `tag_names` (auto-creating
        any that don't exist yet)."""
        tags = self.get_or_create_tags(tag_names, created_by_id)
        self.db.query(CampaignTag).filter(
            CampaignTag.campaign_id == campaign_id
        ).delete(synchronize_session=False)
        self.db.add_all(
            [CampaignTag(campaign_id=campaign_id, tag_id=tag.id) for tag in tags]
        )
        self.db.commit()
        return tags

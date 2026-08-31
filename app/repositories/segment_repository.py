from typing import List, Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.segment import Segment
from app.repositories.soft_delete_repository import SoftDeleteRepository
from app.repositories.segment_resolver import (
    resolve_contacts_query,
    resolve_count,
    validate_campaign_references,
    validate_custom_field_references,
)
from app.schemas.segment import SegmentCreate, SegmentUpdate
from app.schemas.segment_rule import RuleNode, SegmentRuleCreate


class SegmentNameConflictError(ValueError):
    """Raised when a segment name collides with an existing one."""


class SegmentRepository(SoftDeleteRepository[Segment]):
    """Repository class for managing Segment CRUD and resolution."""

    def __init__(self, db: Session):
        super().__init__(db, Segment)

    def get_segment(self, segment_id: UUID) -> Optional[Segment]:
        """Get a single segment by ID."""
        return self.db.query(Segment).filter(Segment.id == segment_id).first()

    def get_segments_query(self):
        """Get a query for all segments, for pagination."""
        return self.db.query(Segment).order_by(Segment.created_at.desc())

    def create_segment(self, segment: SegmentCreate) -> Segment:
        """
        Validate and create a new segment.

        Raises:
            SegmentResolutionError: a campaign_activity leaf references a
                campaign that doesn't exist or isn't completed, or a
                custom_field leaf references an undefined field or a
                mismatched operator.
            SegmentNameConflictError: the name is already taken.
        """
        validate_campaign_references(self.db, segment.rule.root)
        validate_custom_field_references(self.db, segment.rule.root)

        db_segment = Segment(
            name=segment.name,
            rule=segment.rule.model_dump(mode="json"),
            created_by_id=segment.created_by_id,
        )
        self.db.add(db_segment)
        try:
            self.db.commit()
        except IntegrityError as e:
            self.db.rollback()
            raise SegmentNameConflictError(
                f"A segment named {segment.name!r} already exists"
            ) from e
        self.db.refresh(db_segment)
        return db_segment

    def update_segment(
        self, segment_id: UUID, segment: SegmentUpdate
    ) -> Optional[Segment]:
        """
        Update an existing segment's name and/or rule.

        Raises:
            SegmentResolutionError: a campaign_activity leaf references a
                campaign that doesn't exist or isn't completed, or a
                custom_field leaf references an undefined field or a
                mismatched operator.
            SegmentNameConflictError: the new name is already taken.
        """
        db_segment = self.get_segment(segment_id)
        if not db_segment:
            return None

        if segment.rule is not None:
            validate_campaign_references(self.db, segment.rule.root)
            validate_custom_field_references(self.db, segment.rule.root)
            db_segment.rule = segment.rule.model_dump(mode="json")
        if segment.name is not None:
            db_segment.name = segment.name

        try:
            self.db.commit()
        except IntegrityError as e:
            self.db.rollback()
            raise SegmentNameConflictError(
                f"A segment named {segment.name!r} already exists"
            ) from e
        self.db.refresh(db_segment)
        return db_segment

    def delete_segment(self, segment_id: UUID) -> bool:
        """Soft delete a segment."""
        return self.delete_record(segment_id)

    def get_root(self, segment: Segment) -> RuleNode:
        """Parse a persisted segment's stored rule back into a RuleNode."""
        return SegmentRuleCreate.model_validate(segment.rule).root

    def resolve_contacts(self, segment: Segment) -> List:
        """
        The segment's currently resolved contact set.

        Raises:
            SegmentResolutionError: see app.repositories.segment_resolver.
        """
        return resolve_contacts_query(self.db, self.get_root(segment)).all()

    def preview_count(self, segment: Segment) -> int:
        """
        The segment's currently resolved contact count - never persisted,
        always recomputed on demand (see Out of Scope in the PRD).

        Raises:
            SegmentResolutionError: see app.repositories.segment_resolver.
        """
        return resolve_count(self.db, self.get_root(segment))

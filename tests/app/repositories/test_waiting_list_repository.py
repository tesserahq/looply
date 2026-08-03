from app.constants.waiting_list import WaitingListMemberStatus
from app.models.waiting_list_member import WaitingListMember
from app.repositories.waiting_list_repository import WaitingListRepository


class TestReAddRemovedMember:
    """Test re-adding a contact after they were removed from a waiting list."""

    def test_re_add_after_removal_creates_new_active_row(
        self, db, test_waiting_list, test_contact
    ):
        repository = WaitingListRepository(db)

        first_member = repository.add_contact_to_list(
            test_waiting_list.id, test_contact.id, WaitingListMemberStatus.PENDING
        )
        assert first_member is not None

        assert repository.remove_contact_from_list(
            test_waiting_list.id, test_contact.id
        )

        second_member = repository.add_contact_to_list(
            test_waiting_list.id, test_contact.id, WaitingListMemberStatus.PENDING
        )

        assert second_member is not None
        assert second_member.id != first_member.id

        all_rows = (
            db.query(WaitingListMember)
            .execution_options(skip_soft_delete_filter=True)
            .filter(
                WaitingListMember.waiting_list_id == test_waiting_list.id,
                WaitingListMember.contact_id == test_contact.id,
            )
            .all()
        )
        assert len(all_rows) == 2

        removed_row = next(row for row in all_rows if row.id == first_member.id)
        assert removed_row.deleted_at is not None

        active_row = next(row for row in all_rows if row.id == second_member.id)
        assert active_row.deleted_at is None

    def test_second_add_while_still_active_is_rejected(
        self, db, test_waiting_list, test_contact
    ):
        repository = WaitingListRepository(db)

        first_member = repository.add_contact_to_list(
            test_waiting_list.id, test_contact.id, WaitingListMemberStatus.PENDING
        )
        assert first_member is not None

        duplicate_member = repository.add_contact_to_list(
            test_waiting_list.id, test_contact.id, WaitingListMemberStatus.PENDING
        )

        assert duplicate_member is None

"""Custom exception for duplicate contact list member errors."""

from uuid import UUID


class DuplicateContactListMemberError(Exception):
    """Raised when attempting to add a contact that already belongs to a contact list."""

    def __init__(self, contact_list_id: UUID, contact_id: UUID) -> None:
        self.contact_list_id = contact_list_id
        self.contact_id = contact_id
        message = (
            f"Contact {contact_id} is already a member of contact list {contact_list_id}."
        )
        super().__init__(message)

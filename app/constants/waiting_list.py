from enum import Enum


class WaitingListMemberStatus(str, Enum):
    """
    Enum class for managing WaitingList member status values.

    This provides a centralized way to manage status values and avoid
    magic strings throughout the codebase.
    """

    PENDING = "pending"
    """Member is pending approval or notification"""

    APPROVED = "approved"
    """Member has been approved"""

    REJECTED = "rejected"
    """Member has been rejected"""

    NOTIFIED = "notified"
    """Member has been notified"""

    ACCEPTED = "accepted"
    """Member has accepted their spot"""

    DECLINED = "declined"
    """Member has declined their spot"""

    ACTIVE = "active"
    """Member is currently active"""

    INACTIVE = "inactive"
    """Member is currently inactive"""

    CANCELLED = "cancelled"
    """Member has been cancelled"""

    @classmethod
    def values(cls) -> list[str]:
        """
        Get all status values as a list.

        Returns:
            list[str]: List of all status values
        """
        return [status.value for status in cls]

    @classmethod
    def is_valid(cls, status: str) -> bool:
        """
        Check if a status value is valid.

        Args:
            status: The status to validate

        Returns:
            bool: True if status is valid, False otherwise
        """
        try:
            cls(status)
            return True
        except ValueError:
            return False

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        """
        Get status choices for use in forms or APIs.

        Returns:
            list[tuple[str, str]]: List of (value, label) tuples
        """
        return [(status.value, status.value.title()) for status in cls]

    def __str__(self) -> str:
        """Return the string representation of the status."""
        return self.value

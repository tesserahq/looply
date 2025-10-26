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
    def get_description(cls, status: "WaitingListMemberStatus") -> str:
        """
        Get the description for a specific status.

        Args:
            status: The status to get description for

        Returns:
            str: Description of the status
        """
        descriptions = {
            cls.PENDING: "Member is pending approval or notification",
            cls.APPROVED: "Member has been approved",
            cls.REJECTED: "Member has been rejected",
            cls.NOTIFIED: "Member has been notified",
            cls.ACCEPTED: "Member has accepted their spot",
            cls.DECLINED: "Member has declined their spot",
            cls.ACTIVE: "Member is currently active",
            cls.INACTIVE: "Member is currently inactive",
            cls.CANCELLED: "Member has been cancelled",
        }
        return descriptions.get(status, "")

    @classmethod
    def get_all_with_descriptions(cls) -> list[dict]:
        """
        Get all statuses with their values, labels, and descriptions.

        Returns:
            list[dict]: List of dictionaries with value, label, and description
        """
        return [
            {
                "value": status.value,
                "label": status.value.title(),
                "description": cls.get_description(status),
            }
            for status in cls
        ]

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

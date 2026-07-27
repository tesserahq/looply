from enum import Enum


class CampaignStatus(str, Enum):
    """
    Enum class for managing Campaign status values.

    This provides a centralized way to manage status values and avoid
    magic strings throughout the codebase.
    """

    DRAFT = "draft"
    """Campaign has been created but not yet sent."""

    SENDING = "sending"
    """Sendly has accepted the broadcast; delivery is in progress."""

    COMPLETED = "completed"
    """Sendly has finished processing the broadcast."""

    FAILED = "failed"
    """Looply could not get the broadcast accepted by Sendly."""

    @classmethod
    def get_description(cls, status: "CampaignStatus") -> str:
        """
        Get the description for a specific status.

        Args:
            status: The status to get description for

        Returns:
            str: Description of the status
        """
        descriptions = {
            cls.DRAFT: "Campaign has been created but not yet sent",
            cls.SENDING: "Sendly has accepted the broadcast; delivery is in progress",
            cls.COMPLETED: "Sendly has finished processing the broadcast",
            cls.FAILED: "Looply could not get the broadcast accepted by Sendly",
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

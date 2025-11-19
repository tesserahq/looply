from enum import Enum


class ContactInteractionAction(str, Enum):
    """
    Enum class for managing ContactInteraction action values.

    This provides a centralized way to manage action values and avoid
    magic strings throughout the codebase.
    """

    FOLLOW_UP_CALL = "follow_up_call"
    """Schedule a follow-up phone call"""

    FOLLOW_UP_EMAIL = "follow_up_email"
    """Send a follow-up email"""

    SCHEDULE_MEETING = "schedule_meeting"
    """Schedule a meeting"""

    SEND_PROPOSAL = "send_proposal"
    """Send a proposal"""

    REVIEW_PROPOSAL = "review_proposal"
    """Review a proposal"""

    SEND_CONTRACT = "send_contract"
    """Send a contract"""

    SEND_DOCUMENTATION = "send_documentation"
    """Send documentation"""

    SCHEDULE_DEMO = "schedule_demo"
    """Schedule a product demo"""

    CHECK_IN = "check_in"
    """Check in with the contact"""

    SEND_QUOTE = "send_quote"
    """Send a quote"""

    FOLLOW_UP_IN_WEEKS = "follow_up_in_weeks"
    """Follow up in a few weeks"""

    FOLLOW_UP_IN_MONTHS = "follow_up_in_months"
    """Follow up in a few months"""

    SEND_INVOICE = "send_invoice"
    """Send an invoice"""

    REQUEST_FEEDBACK = "request_feedback"
    """Request feedback"""

    SEND_THANK_YOU = "send_thank_you"
    """Send a thank you message"""

    ONBOARDING_CALL = "onboarding_call"
    """Schedule an onboarding call"""

    TRAINING_SESSION = "training_session"
    """Schedule a training session"""

    CUSTOM = "custom"
    """Custom action (user-defined)"""

    @classmethod
    def get_label(cls, action: "ContactInteractionAction") -> str:
        """
        Get the human-readable label for a specific action.

        Args:
            action: The action to get label for

        Returns:
            str: Label of the action
        """
        labels = {
            cls.FOLLOW_UP_CALL: "Follow Up Call",
            cls.FOLLOW_UP_EMAIL: "Follow Up Email",
            cls.SCHEDULE_MEETING: "Schedule Meeting",
            cls.SEND_PROPOSAL: "Send Proposal",
            cls.REVIEW_PROPOSAL: "Review Proposal",
            cls.SEND_CONTRACT: "Send Contract",
            cls.SEND_DOCUMENTATION: "Send Documentation",
            cls.SCHEDULE_DEMO: "Schedule Demo",
            cls.CHECK_IN: "Check In",
            cls.SEND_QUOTE: "Send Quote",
            cls.FOLLOW_UP_IN_WEEKS: "Follow Up in Weeks",
            cls.FOLLOW_UP_IN_MONTHS: "Follow Up in Months",
            cls.SEND_INVOICE: "Send Invoice",
            cls.REQUEST_FEEDBACK: "Request Feedback",
            cls.SEND_THANK_YOU: "Send Thank You",
            cls.ONBOARDING_CALL: "Onboarding Call",
            cls.TRAINING_SESSION: "Training Session",
            cls.CUSTOM: "Custom",
        }
        return labels.get(action, action.value.replace("_", " ").title())

    @classmethod
    def get_description(cls, action: "ContactInteractionAction") -> str:
        """
        Get the description for a specific action.

        Args:
            action: The action to get description for

        Returns:
            str: Description of the action
        """
        descriptions = {
            cls.FOLLOW_UP_CALL: "Schedule a follow-up phone call",
            cls.FOLLOW_UP_EMAIL: "Send a follow-up email",
            cls.SCHEDULE_MEETING: "Schedule a meeting",
            cls.SEND_PROPOSAL: "Send a proposal",
            cls.REVIEW_PROPOSAL: "Review a proposal",
            cls.SEND_CONTRACT: "Send a contract",
            cls.SEND_DOCUMENTATION: "Send documentation",
            cls.SCHEDULE_DEMO: "Schedule a product demo",
            cls.CHECK_IN: "Check in with the contact",
            cls.SEND_QUOTE: "Send a quote",
            cls.FOLLOW_UP_IN_WEEKS: "Follow up in a few weeks",
            cls.FOLLOW_UP_IN_MONTHS: "Follow up in a few months",
            cls.SEND_INVOICE: "Send an invoice",
            cls.REQUEST_FEEDBACK: "Request feedback",
            cls.SEND_THANK_YOU: "Send a thank you message",
            cls.ONBOARDING_CALL: "Schedule an onboarding call",
            cls.TRAINING_SESSION: "Schedule a training session",
            cls.CUSTOM: "Custom action (user-defined)",
        }
        return descriptions.get(action, "")

    @classmethod
    def get_all_with_labels(cls) -> list[dict]:
        """
        Get all actions with their values and labels.

        Returns:
            list[dict]: List of dictionaries with value and label
        """
        return [
            {
                "value": action.value,
                "label": cls.get_label(action),
            }
            for action in cls
        ]

    @classmethod
    def get_all_with_descriptions(cls) -> list[dict]:
        """
        Get all actions with their values, labels, and descriptions.

        Returns:
            list[dict]: List of dictionaries with value, label, and description
        """
        return [
            {
                "value": action.value,
                "label": cls.get_label(action),
                "description": cls.get_description(action),
            }
            for action in cls
        ]

    @classmethod
    def values(cls) -> list[str]:
        """
        Get all action values as a list.

        Returns:
            list[str]: List of all action values
        """
        return [action.value for action in cls]

    @classmethod
    def is_valid(cls, action: str) -> bool:
        """
        Check if an action value is valid.

        Args:
            action: The action to validate

        Returns:
            bool: True if action is valid, False otherwise
        """
        try:
            cls(action)
            return True
        except ValueError:
            return False

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        """
        Get action choices for use in forms or APIs.

        Returns:
            list[tuple[str, str]]: List of (value, label) tuples
        """
        return [(action.value, cls.get_label(action)) for action in cls]

    def __str__(self) -> str:
        """Return the string representation of the action."""
        return self.value

import pytest
from datetime import datetime, timezone, timedelta
from app.models.contact_interaction import ContactInteraction


@pytest.fixture(scope="function")
def test_contact_interaction(db, faker, test_user, test_contact):
    """Create a test contact interaction for use in tests."""
    interaction_data = {
        "contact_id": test_contact.id,
        "note": faker.text(max_nb_chars=500),
        "interaction_timestamp": datetime.now(timezone.utc),
        "action": None,
        "action_timestamp": None,
        "created_by_id": test_user.id,
    }

    interaction = ContactInteraction(**interaction_data)
    db.add(interaction)
    db.commit()
    db.refresh(interaction)

    return interaction


@pytest.fixture(scope="function")
def setup_contact_interaction(db, faker, setup_user, setup_contact):
    """Create a test contact interaction for use in tests."""
    interaction_data = {
        "contact_id": setup_contact.id,
        "note": faker.text(max_nb_chars=800),
        "interaction_timestamp": datetime.now(timezone.utc),
        "action": "Follow up next week",
        "action_timestamp": datetime.now(timezone.utc) + timedelta(days=7),
        "created_by_id": setup_user.id,
    }

    interaction = ContactInteraction(**interaction_data)
    db.add(interaction)
    db.commit()
    db.refresh(interaction)

    return interaction


@pytest.fixture(scope="function")
def interaction_with_pending_action(db, faker, test_user, test_contact):
    """Create a contact interaction with a pending action in the future."""
    interaction_data = {
        "contact_id": test_contact.id,
        "note": faker.text(max_nb_chars=600),
        "interaction_timestamp": datetime.now(timezone.utc) - timedelta(days=1),
        "action": "Send proposal",
        "action_timestamp": datetime.now(timezone.utc) + timedelta(days=3),
        "created_by_id": test_user.id,
    }

    interaction = ContactInteraction(**interaction_data)
    db.add(interaction)
    db.commit()
    db.refresh(interaction)

    return interaction


@pytest.fixture(scope="function")
def interaction_with_past_action(db, faker, test_user, test_contact):
    """Create a contact interaction with an action in the past (completed)."""
    interaction_data = {
        "contact_id": test_contact.id,
        "note": faker.text(max_nb_chars=400),
        "interaction_timestamp": datetime.now(timezone.utc) - timedelta(days=5),
        "action": "Follow up call",
        "action_timestamp": datetime.now(timezone.utc) - timedelta(days=2),
        "created_by_id": test_user.id,
    }

    interaction = ContactInteraction(**interaction_data)
    db.add(interaction)
    db.commit()
    db.refresh(interaction)

    return interaction


@pytest.fixture(scope="function")
def interaction_with_no_action_timestamp(db, faker, test_user, test_contact):
    """Create a contact interaction with an action but no action_timestamp."""
    interaction_data = {
        "contact_id": test_contact.id,
        "note": faker.text(max_nb_chars=700),
        "interaction_timestamp": datetime.now(timezone.utc),
        "action": "Review proposal",
        "action_timestamp": None,
        "created_by_id": test_user.id,
    }

    interaction = ContactInteraction(**interaction_data)
    db.add(interaction)
    db.commit()
    db.refresh(interaction)

    return interaction


@pytest.fixture(scope="function")
def multiple_interactions_for_contact(db, faker, test_user, test_contact):
    """Create multiple interactions for the same contact."""
    interactions = []
    base_time = datetime.now(timezone.utc)

    for i in range(5):
        interaction_data = {
            "contact_id": test_contact.id,
            "note": faker.text(max_nb_chars=500),
            "interaction_timestamp": base_time - timedelta(days=i),
            "action": f"Action {i}" if i % 2 == 0 else None,
            "action_timestamp": (
                base_time + timedelta(days=i + 1) if i % 2 == 0 else None
            ),
            "created_by_id": test_user.id,
        }

        interaction = ContactInteraction(**interaction_data)
        db.add(interaction)
        interactions.append(interaction)

    db.commit()
    for interaction in interactions:
        db.refresh(interaction)

    return interactions

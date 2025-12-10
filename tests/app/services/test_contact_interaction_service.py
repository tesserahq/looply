import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from app.schemas.contact_interaction import (
    ContactInteractionCreate,
    ContactInteractionUpdate,
)
from app.services.contact_interaction_service import ContactInteractionService


@pytest.fixture
def sample_interaction_data(faker, test_user, test_contact):
    return {
        "contact_id": test_contact.id,
        "note": faker.text(max_nb_chars=500),
        "interaction_timestamp": datetime.now(timezone.utc),
        "action": "Follow up in 2 weeks",
        "action_timestamp": datetime.now(timezone.utc) + timedelta(days=14),
        "created_by_id": test_user.id,
    }


@pytest.fixture
def minimal_interaction_data(faker, test_user, test_contact):
    return {
        "contact_id": test_contact.id,
        "note": faker.text(max_nb_chars=300),
        "interaction_timestamp": datetime.now(timezone.utc),
        "created_by_id": test_user.id,
    }


def test_create_contact_interaction(db, sample_interaction_data):
    """Test creating a contact interaction with full data."""
    interaction_create = ContactInteractionCreate(**sample_interaction_data)
    interaction = ContactInteractionService(db).create_contact_interaction(
        interaction_create
    )

    # Assertions
    assert interaction.id is not None
    assert interaction.contact_id == sample_interaction_data["contact_id"]
    assert interaction.note == sample_interaction_data["note"]
    assert (
        interaction.interaction_timestamp
        == sample_interaction_data["interaction_timestamp"]
    )
    assert interaction.action == sample_interaction_data["action"]
    assert interaction.action_timestamp == sample_interaction_data["action_timestamp"]
    assert interaction.created_by_id == sample_interaction_data["created_by_id"]
    assert interaction.created_at is not None
    assert interaction.updated_at is not None


def test_create_contact_interaction_minimal_data(db, minimal_interaction_data):
    """Test creating a contact interaction with minimal required data."""
    interaction_create = ContactInteractionCreate(**minimal_interaction_data)
    interaction = ContactInteractionService(db).create_contact_interaction(
        interaction_create
    )

    # Assertions
    assert interaction.id is not None
    assert interaction.contact_id == minimal_interaction_data["contact_id"]
    assert interaction.note == minimal_interaction_data["note"]
    assert interaction.action is None
    assert interaction.action_timestamp is None
    assert interaction.created_by_id == minimal_interaction_data["created_by_id"]
    assert interaction.created_at is not None
    assert interaction.updated_at is not None


def test_get_contact_interaction(db, test_contact_interaction):
    """Test retrieving a contact interaction by ID."""
    retrieved_interaction = ContactInteractionService(db).get_contact_interaction(
        test_contact_interaction.id
    )

    # Assertions
    assert retrieved_interaction is not None
    assert retrieved_interaction.id == test_contact_interaction.id
    assert retrieved_interaction.note == test_contact_interaction.note
    assert retrieved_interaction.contact_id == test_contact_interaction.contact_id


def test_get_contact_interactions(db, test_contact_interaction):
    """Test retrieving all contact interactions with pagination."""
    interactions = ContactInteractionService(db).get_contact_interactions()

    # Assertions
    assert len(interactions) >= 1
    assert any(i.id == test_contact_interaction.id for i in interactions)


def test_get_contact_interactions_with_pagination(
    db, multiple_interactions_for_contact
):
    """Test retrieving contact interactions with pagination."""
    service = ContactInteractionService(db)

    # Get first page
    interactions_page1 = service.get_contact_interactions(skip=0, limit=2)
    assert len(interactions_page1) == 2

    # Get second page
    interactions_page2 = service.get_contact_interactions(skip=2, limit=2)
    assert len(interactions_page2) == 2

    # Verify they're different
    ids_page1 = {i.id for i in interactions_page1}
    ids_page2 = {i.id for i in interactions_page2}
    assert ids_page1.isdisjoint(ids_page2)


def test_get_interactions_by_contact(db, test_contact, test_contact_interaction):
    """Test retrieving interactions for a specific contact."""
    interactions = ContactInteractionService(db).get_interactions_by_contact(
        test_contact.id
    )

    # Assertions
    assert len(interactions) >= 1
    assert any(i.id == test_contact_interaction.id for i in interactions)
    assert all(i.contact_id == test_contact.id for i in interactions)


def test_get_interactions_by_contact_empty(db, setup_contact):
    """Test retrieving interactions for a contact with no interactions."""
    interactions = ContactInteractionService(db).get_interactions_by_contact(
        setup_contact.id
    )

    # Assertions
    assert len(interactions) == 0


def test_get_last_interaction(db, test_contact, multiple_interactions_for_contact):
    """Test retrieving the most recent interaction for a contact."""
    last_interaction = ContactInteractionService(db).get_last_interaction(
        test_contact.id
    )

    # Assertions
    assert last_interaction is not None
    # The last interaction should be the one with the most recent timestamp
    assert last_interaction.id == multiple_interactions_for_contact[0].id


def test_get_last_interaction_none(db, setup_contact):
    """Test retrieving last interaction for a contact with no interactions."""
    last_interaction = ContactInteractionService(db).get_last_interaction(
        setup_contact.id
    )

    # Assertions
    assert last_interaction is None


def test_get_pending_actions(
    db,
    interaction_with_pending_action,
    interaction_with_past_action,
    interaction_with_no_action_timestamp,
):
    """Test retrieving all pending actions."""
    pending_actions = ContactInteractionService(db).get_pending_actions()

    # Assertions
    assert len(pending_actions) >= 2
    # Should include interactions with future action_timestamp
    assert any(i.id == interaction_with_pending_action.id for i in pending_actions)
    # Should include interactions with action but no action_timestamp
    assert any(i.id == interaction_with_no_action_timestamp.id for i in pending_actions)
    # Should NOT include interactions with past action_timestamp
    assert not any(i.id == interaction_with_past_action.id for i in pending_actions)


def test_get_pending_actions_by_contact(
    db,
    test_contact,
    interaction_with_pending_action,
    interaction_with_no_action_timestamp,
):
    """Test retrieving pending actions for a specific contact."""
    pending_actions = ContactInteractionService(db).get_pending_actions_by_contact(
        test_contact.id
    )

    # Assertions
    assert len(pending_actions) >= 2
    assert all(i.contact_id == test_contact.id for i in pending_actions)
    assert any(i.id == interaction_with_pending_action.id for i in pending_actions)
    assert any(i.id == interaction_with_no_action_timestamp.id for i in pending_actions)


def test_get_pending_actions_by_contact_empty(db, setup_contact):
    """Test retrieving pending actions for a contact with no pending actions."""
    pending_actions = ContactInteractionService(db).get_pending_actions_by_contact(
        setup_contact.id
    )

    # Assertions
    assert len(pending_actions) == 0


def test_update_contact_interaction(db, test_contact_interaction):
    """Test updating a contact interaction."""
    update_data = {
        "note": "Updated note text",
        "action": "Updated action",
        "action_timestamp": datetime.now(timezone.utc) + timedelta(days=5),
    }
    interaction_update = ContactInteractionUpdate(**update_data)

    # Update interaction
    updated_interaction = ContactInteractionService(db).update_contact_interaction(
        test_contact_interaction.id, interaction_update
    )

    # Assertions
    assert updated_interaction is not None
    assert updated_interaction.id == test_contact_interaction.id
    assert updated_interaction.note == update_data["note"]
    assert updated_interaction.action == update_data["action"]
    assert updated_interaction.action_timestamp == update_data["action_timestamp"]
    # Verify other fields remain unchanged
    assert updated_interaction.contact_id == test_contact_interaction.contact_id
    assert updated_interaction.created_by_id == test_contact_interaction.created_by_id


def test_update_contact_interaction_partial(db, test_contact_interaction):
    """Test updating a contact interaction with partial data."""
    update_data = {"note": "Only note updated"}
    interaction_update = ContactInteractionUpdate(**update_data)

    # Update interaction
    updated_interaction = ContactInteractionService(db).update_contact_interaction(
        test_contact_interaction.id, interaction_update
    )

    # Assertions
    assert updated_interaction is not None
    assert updated_interaction.note == update_data["note"]
    # Verify other fields remain unchanged
    if test_contact_interaction.action:
        assert updated_interaction.action == test_contact_interaction.action
    assert updated_interaction.contact_id == test_contact_interaction.contact_id


def test_update_contact_interaction_clear_action(db, setup_contact_interaction):
    """Test clearing an action from a contact interaction."""
    update_data = {"action": None, "action_timestamp": None}
    interaction_update = ContactInteractionUpdate(**update_data)

    # Update interaction
    updated_interaction = ContactInteractionService(db).update_contact_interaction(
        setup_contact_interaction.id, interaction_update
    )

    # Assertions
    assert updated_interaction is not None
    assert updated_interaction.action is None
    assert updated_interaction.action_timestamp is None


def test_delete_contact_interaction(db, test_contact_interaction):
    """Test soft deleting a contact interaction."""
    interaction_service = ContactInteractionService(db)

    # Delete interaction
    success = interaction_service.delete_contact_interaction(
        test_contact_interaction.id
    )

    # Assertions
    assert success is True
    deleted_interaction = interaction_service.get_contact_interaction(
        test_contact_interaction.id
    )
    assert deleted_interaction is None


def test_contact_interaction_not_found_cases(db):
    """Test various not found cases."""
    interaction_service = ContactInteractionService(db)
    non_existent_id = uuid4()

    # Get non-existent interaction
    assert interaction_service.get_contact_interaction(non_existent_id) is None

    # Update non-existent interaction
    update_data = {"note": "Updated"}
    interaction_update = ContactInteractionUpdate(**update_data)
    assert (
        interaction_service.update_contact_interaction(
            non_existent_id, interaction_update
        )
        is None
    )

    # Delete non-existent interaction
    assert interaction_service.delete_contact_interaction(non_existent_id) is False


def test_search_interactions_with_filters(db, test_contact_interaction):
    """Test searching interactions with dynamic filters."""
    # Search by contact_id
    filters = {"contact_id": str(test_contact_interaction.contact_id)}
    results = ContactInteractionService(db).search(filters)

    assert isinstance(results, list)
    assert any(interaction.id == test_contact_interaction.id for interaction in results)

    # Search with no match
    filters = {"contact_id": str(uuid4())}
    results = ContactInteractionService(db).search(filters)

    assert len(results) == 0


def test_get_contact_interactions_query(db, test_contact_interaction):
    """Test getting the query object for contact interactions."""
    query = ContactInteractionService(db).get_contact_interactions_query()

    # Assertions
    assert query is not None
    results = query.all()
    assert len(results) >= 1
    assert any(i.id == test_contact_interaction.id for i in results)


def test_get_interactions_by_contact_query(db, test_contact, test_contact_interaction):
    """Test getting the query object for interactions by contact."""
    query = ContactInteractionService(db).get_interactions_by_contact_query(
        test_contact.id
    )

    # Assertions
    assert query is not None
    results = query.all()
    assert len(results) >= 1
    assert all(i.contact_id == test_contact.id for i in results)
    assert any(i.id == test_contact_interaction.id for i in results)


def test_interactions_ordered_by_timestamp(
    db, test_contact, multiple_interactions_for_contact
):
    """Test that interactions are ordered by timestamp (most recent first)."""
    interactions = ContactInteractionService(db).get_interactions_by_contact(
        test_contact.id
    )

    # Assertions
    assert len(interactions) >= 5
    # Verify they're in descending order
    timestamps = [i.interaction_timestamp for i in interactions]
    assert timestamps == sorted(timestamps, reverse=True)


def test_pending_actions_ordered_by_timestamp(
    db,
    interaction_with_pending_action,
    interaction_with_no_action_timestamp,
):
    """Test that pending actions are ordered by action_timestamp (ascending, nulls last)."""
    pending_actions = ContactInteractionService(db).get_pending_actions()

    # Assertions
    assert len(pending_actions) >= 2
    # Verify ordering: nulls should be last, then ascending by timestamp
    action_timestamps = [
        i.action_timestamp for i in pending_actions if i.action_timestamp is not None
    ]
    null_count = sum(1 for i in pending_actions if i.action_timestamp is None)

    # All non-null timestamps should be in ascending order
    if len(action_timestamps) > 1:
        assert action_timestamps == sorted(action_timestamps)

    # Nulls should be at the end
    if null_count > 0:
        last_items = pending_actions[-null_count:]
        assert all(i.action_timestamp is None for i in last_items)


def test_restore_contact_interaction(db, test_contact_interaction):
    """Test restoring a soft-deleted contact interaction."""
    interaction_service = ContactInteractionService(db)

    # First delete the interaction
    interaction_service.delete_contact_interaction(test_contact_interaction.id)
    assert (
        interaction_service.get_contact_interaction(test_contact_interaction.id) is None
    )

    # Then restore it
    success = interaction_service.restore_record(test_contact_interaction.id)
    assert success is True

    # Verify it's restored
    restored_interaction = interaction_service.get_contact_interaction(
        test_contact_interaction.id
    )
    assert restored_interaction is not None
    assert restored_interaction.id == test_contact_interaction.id


def test_hard_delete_contact_interaction(db, test_contact_interaction):
    """Test hard deleting a contact interaction."""
    interaction_service = ContactInteractionService(db)

    # Hard delete the interaction
    success = interaction_service.hard_delete_record(test_contact_interaction.id)
    assert success is True

    # Verify it's permanently deleted
    deleted_interaction = interaction_service.get_contact_interaction(
        test_contact_interaction.id
    )
    assert deleted_interaction is None


def test_get_deleted_interactions(db, test_contact_interaction):
    """Test getting soft-deleted interactions."""
    interaction_service = ContactInteractionService(db)

    # Delete the interaction
    interaction_service.delete_contact_interaction(test_contact_interaction.id)

    # Get deleted interactions
    deleted_interactions = interaction_service.get_deleted_records()
    assert len(deleted_interactions) >= 1
    assert any(i.id == test_contact_interaction.id for i in deleted_interactions)

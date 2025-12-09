from uuid import uuid4
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.constants.contact_interaction import ContactInteractionAction


class TestContactInteractionActions:
    """Test class for contact interaction actions endpoint."""

    def test_list_actions(self, client):
        """Test GET /contact-interactions/actions endpoint."""
        response = client.get("/contact-interactions/actions")
        assert response.status_code == 200

        data = response.json()
        # Check response structure
        assert "items" in data
        assert "size" in data
        assert "page" in data
        assert "pages" in data
        assert "total" in data

        # Check pagination values
        assert data["page"] == 1
        assert data["pages"] == 1
        assert data["size"] == data["total"]
        assert data["size"] == len(data["items"])

        # Check items structure
        assert len(data["items"]) > 0
        for item in data["items"]:
            assert "value" in item
            assert "label" in item
            assert isinstance(item["value"], str)
            assert isinstance(item["label"], str)

        # Verify all expected actions are present
        expected_actions = ContactInteractionAction.get_all_with_labels()
        assert len(data["items"]) == len(expected_actions)

        # Verify specific actions exist
        action_values = [item["value"] for item in data["items"]]
        assert ContactInteractionAction.FOLLOW_UP_CALL.value in action_values
        assert ContactInteractionAction.FOLLOW_UP_EMAIL.value in action_values
        assert ContactInteractionAction.SCHEDULE_MEETING.value in action_values
        assert ContactInteractionAction.CUSTOM.value in action_values


class TestContactInteractionRouter:
    """Test class for contact interaction router endpoints."""

    def test_create_contact_interaction(self, client, test_contact, faker):
        """Test POST /contacts/{contact_id}/interactions endpoint."""
        interaction_data = {
            "note": faker.text(max_nb_chars=500),
            "interaction_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        response = client.post(
            f"/contacts/{test_contact.id}/interactions", json=interaction_data
        )
        assert response.status_code == 201

        data = response.json()
        assert data["contact_id"] == str(test_contact.id)
        assert data["note"] == interaction_data["note"]
        assert data["id"] is not None
        assert data["created_by_id"] == str(client.app.state.test_user.id)

    def test_create_contact_interaction_with_action(self, client, test_contact, faker):
        """Test POST /contacts/{contact_id}/interactions with action."""
        interaction_data = {
            "note": faker.text(max_nb_chars=500),
            "interaction_timestamp": datetime.now(timezone.utc).isoformat(),
            "action": ContactInteractionAction.FOLLOW_UP_CALL.value,
            "action_timestamp": (
                datetime.now(timezone.utc) + timedelta(days=7)
            ).isoformat(),
        }

        response = client.post(
            f"/contacts/{test_contact.id}/interactions", json=interaction_data
        )
        assert response.status_code == 201

        data = response.json()
        assert data["action"] == interaction_data["action"]
        assert data["action_timestamp"] is not None

    def test_create_contact_interaction_minimal(self, client, test_contact, faker):
        """Test POST /contacts/{contact_id}/interactions with minimal data."""
        interaction_data = {
            "note": faker.text(max_nb_chars=200),
        }

        response = client.post(
            f"/contacts/{test_contact.id}/interactions", json=interaction_data
        )
        assert response.status_code == 201

        data = response.json()
        assert data["note"] == interaction_data["note"]
        assert data["interaction_timestamp"] is not None  # Should be auto-set

    def test_create_contact_interaction_contact_not_found(self, client, faker):
        """Test POST /contacts/{contact_id}/interactions with non-existent contact."""
        fake_contact_id = uuid4()
        interaction_data = {
            "note": faker.text(max_nb_chars=200),
        }

        response = client.post(
            f"/contacts/{fake_contact_id}/interactions", json=interaction_data
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_list_contact_interactions(
        self,
        client,
        test_contact,
        multiple_interactions_for_contact,
    ):
        """Test GET /contacts/{contact_id}/interactions endpoint."""
        response = client.get(f"/contacts/{test_contact.id}/interactions")
        assert response.status_code == 200

        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "size" in data
        assert "pages" in data

        # Should have at least the interactions we created
        assert data["total"] >= 5
        assert len(data["items"]) >= 5

        # All interactions should belong to the contact
        for item in data["items"]:
            assert item["contact_id"] == str(test_contact.id)

    def test_list_contact_interactions_empty(self, client, test_contact):
        """Test GET /contacts/{contact_id}/interactions with no interactions."""
        response = client.get(f"/contacts/{test_contact.id}/interactions")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0

    def test_list_contact_interactions_pagination(
        self,
        client,
        test_contact,
        multiple_interactions_for_contact,
    ):
        """Test GET /contacts/{contact_id}/interactions with pagination."""
        response = client.get(f"/contacts/{test_contact.id}/interactions?page=1&size=2")
        assert response.status_code == 200

        data = response.json()
        assert data["page"] == 1
        assert data["size"] == 2
        assert len(data["items"]) <= 2

    def test_get_last_contact_interaction(
        self,
        client,
        test_contact,
        multiple_interactions_for_contact,
    ):
        """Test GET /contacts/{contact_id}/interactions/last endpoint."""
        response = client.get(f"/contacts/{test_contact.id}/interactions/last")
        assert response.status_code == 200

        data = response.json()
        assert data["contact_id"] == str(test_contact.id)
        assert data["id"] is not None

        # Verify it's the most recent (should have the latest interaction_timestamp)
        all_response = client.get(f"/contacts/{test_contact.id}/interactions")
        all_data = all_response.json()
        if len(all_data["items"]) > 0:
            # The last interaction should be the one with the most recent timestamp
            latest = max(
                all_data["items"],
                key=lambda x: x["interaction_timestamp"],
            )
            assert data["interaction_timestamp"] == latest["interaction_timestamp"]

    def test_get_last_contact_interaction_not_found(self, client, test_contact):
        """Test GET /contacts/{contact_id}/interactions/last with no interactions."""
        response = client.get(f"/contacts/{test_contact.id}/interactions/last")
        assert response.status_code == 404
        assert "no interactions found" in response.json()["detail"].lower()

    def test_get_contact_interaction(self, client, test_contact_interaction):
        """Test GET /contact-interactions/{interaction_id} endpoint."""
        response = client.get(f"/contact-interactions/{test_contact_interaction.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == str(test_contact_interaction.id)
        assert data["contact_id"] == str(test_contact_interaction.contact_id)
        assert data["note"] == test_contact_interaction.note

    def test_get_contact_interaction_not_found(self, client):
        """Test GET /contact-interactions/{interaction_id} with non-existent ID."""
        fake_id = uuid4()
        response = client.get(f"/contact-interactions/{fake_id}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_update_contact_interaction(self, client, test_contact_interaction, faker):
        """Test PUT /contact-interactions/{interaction_id} endpoint."""
        update_data = {
            "note": "Updated note",
            "action": ContactInteractionAction.SCHEDULE_MEETING.value,
        }

        response = client.put(
            f"/contact-interactions/{test_contact_interaction.id}", json=update_data
        )
        assert response.status_code == 200

        data = response.json()
        assert data["note"] == update_data["note"]
        assert data["action"] == update_data["action"]

    def test_update_contact_interaction_partial(
        self, client, test_contact_interaction, faker
    ):
        """Test PUT /contact-interactions/{interaction_id} with partial update."""
        original_note = test_contact_interaction.note
        update_data = {
            "action": ContactInteractionAction.FOLLOW_UP_EMAIL.value,
        }

        response = client.put(
            f"/contact-interactions/{test_contact_interaction.id}", json=update_data
        )
        assert response.status_code == 200

        data = response.json()
        assert data["note"] == original_note  # Should remain unchanged
        assert data["action"] == update_data["action"]

    def test_update_contact_interaction_not_found(self, client, faker):
        """Test PUT /contact-interactions/{interaction_id} with non-existent ID."""
        fake_id = uuid4()
        update_data = {"note": "Updated note"}

        response = client.put(f"/contact-interactions/{fake_id}", json=update_data)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_delete_contact_interaction(self, client, test_contact_interaction):
        """Test DELETE /contact-interactions/{interaction_id} endpoint."""
        interaction_id = test_contact_interaction.id
        response = client.delete(f"/contact-interactions/{interaction_id}")
        assert response.status_code == 204

        # Verify interaction is soft deleted
        get_response = client.get(f"/contact-interactions/{interaction_id}")
        assert get_response.status_code == 404

    def test_delete_contact_interaction_not_found(self, client):
        """Test DELETE /contact-interactions/{interaction_id} with non-existent ID."""
        fake_id = uuid4()
        response = client.delete(f"/contact-interactions/{fake_id}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_list_contact_interactions_global(
        self,
        client,
        test_contact_interaction,
        setup_contact_interaction,
    ):
        """Test GET /contact-interactions endpoint (global list)."""
        response = client.get("/contact-interactions")
        assert response.status_code == 200

        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "size" in data
        assert "pages" in data

        # Should have at least 2 interactions
        assert data["total"] >= 2
        assert len(data["items"]) >= 2

    def test_list_contact_interactions_global_pagination(
        self,
        client,
        test_contact_interaction,
        setup_contact_interaction,
    ):
        """Test GET /contact-interactions with pagination."""
        response = client.get("/contact-interactions?page=1&size=1")
        assert response.status_code == 200

        data = response.json()
        assert data["page"] == 1
        assert data["size"] == 1
        assert len(data["items"]) <= 1

    def test_get_pending_actions(
        self,
        client,
        interaction_with_pending_action,
        interaction_with_no_action_timestamp,
        interaction_with_past_action,
    ):
        """Test GET /contact-interactions/pending-actions endpoint."""
        response = client.get("/contact-interactions/pending-actions")
        assert response.status_code == 200

        data = response.json()
        assert "items" in data
        assert "total" in data

        # Should include pending actions
        assert data["total"] >= 2

        # Verify pending actions are included
        item_ids = [item["id"] for item in data["items"]]
        assert str(interaction_with_pending_action.id) in item_ids
        assert str(interaction_with_no_action_timestamp.id) in item_ids

        # Should NOT include past actions
        assert str(interaction_with_past_action.id) not in item_ids

    def test_get_pending_actions_empty(self, client):
        """Test GET /contact-interactions/pending-actions with no pending actions."""
        response = client.get("/contact-interactions/pending-actions")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0

    def test_get_pending_actions_pagination(
        self,
        client,
        interaction_with_pending_action,
        interaction_with_no_action_timestamp,
    ):
        """Test GET /contact-interactions/pending-actions with pagination."""
        response = client.get("/contact-interactions/pending-actions?page=1&size=1")
        assert response.status_code == 200

        data = response.json()
        assert data["page"] == 1
        assert data["size"] == 1
        assert len(data["items"]) <= 1

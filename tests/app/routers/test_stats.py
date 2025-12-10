from datetime import datetime, timezone, timedelta
from app.models.contact import Contact
from app.models.contact_list import ContactList
from app.models.contact_interaction import ContactInteraction


class TestStatsRouter:
    """Test class for stats router endpoints."""

    def test_get_stats_empty_database(self, client):
        """Test GET /stats endpoint with empty database."""
        response = client.get("/stats")
        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        stats = data["data"]

        assert stats["total_contacts"] == 0
        assert stats["total_list"] == 0
        assert stats["total_public_list"] == 0
        assert stats["total_private_list"] == 0
        assert stats["upcoming_interactions"] == []
        assert stats["recent_contacts"] == []

    def test_get_stats_with_contacts(self, client, test_contact, setup_contact):
        """Test GET /stats endpoint with contacts."""
        response = client.get("/stats")
        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        stats = data["data"]

        assert stats["total_contacts"] == 2
        assert stats["total_list"] == 0
        assert stats["total_public_list"] == 0
        assert stats["total_private_list"] == 0
        assert stats["upcoming_interactions"] == []
        assert len(stats["recent_contacts"]) == 2
        # Verify recent_contacts are sorted by created_at descending (most recent first)
        assert stats["recent_contacts"][0]["id"] in [
            str(test_contact.id),
            str(setup_contact.id),
        ]
        assert stats["recent_contacts"][1]["id"] in [
            str(test_contact.id),
            str(setup_contact.id),
        ]

    def test_get_stats_with_contact_lists(
        self, client, test_contact_list, public_contact_list
    ):
        """Test GET /stats endpoint with contact lists."""
        response = client.get("/stats")
        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        stats = data["data"]

        assert stats["total_contacts"] == 0
        assert stats["total_list"] == 2
        assert stats["total_public_list"] == 1
        assert stats["total_private_list"] == 1
        assert stats["recent_contacts"] == []

    def test_get_stats_with_upcoming_interactions(
        self, client, test_contact, interaction_with_pending_action
    ):
        """Test GET /stats endpoint with upcoming interactions within 5 days."""
        response = client.get("/stats")
        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        stats = data["data"]

        assert stats["total_contacts"] == 1
        assert len(stats["upcoming_interactions"]) == 1
        interaction = stats["upcoming_interactions"][0]
        assert interaction["id"] == str(interaction_with_pending_action.id)
        assert interaction["action"] is not None
        assert interaction["action_timestamp"] is not None

        # Verify contact information is included
        assert "contact" in interaction
        assert interaction["contact"]["id"] == str(test_contact.id)
        assert interaction["contact"]["first_name"] == test_contact.first_name
        assert interaction["contact"]["last_name"] == test_contact.last_name
        assert interaction["contact"]["email"] == test_contact.email

    def test_get_stats_excludes_past_interactions(
        self, client, test_contact, interaction_with_past_action
    ):
        """Test GET /stats endpoint excludes interactions with past action timestamps."""
        response = client.get("/stats")
        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        stats = data["data"]

        assert stats["total_contacts"] == 1
        assert len(stats["upcoming_interactions"]) == 0

    def test_get_stats_excludes_interactions_beyond_5_days(
        self, client, db, test_contact, faker, test_user
    ):
        """Test GET /stats endpoint excludes interactions beyond 5 days."""
        # Create an interaction with action 6 days in the future
        interaction_data = {
            "contact_id": test_contact.id,
            "note": faker.text(max_nb_chars=500),
            "interaction_timestamp": datetime.now(timezone.utc),
            "action": "Follow up in 6 days",
            "action_timestamp": datetime.now(timezone.utc) + timedelta(days=6),
            "created_by_id": test_user.id,
        }

        future_interaction = ContactInteraction(**interaction_data)
        db.add(future_interaction)
        db.commit()
        db.refresh(future_interaction)

        # Create an interaction with action 3 days in the future (should be included)
        interaction_data_3_days = {
            "contact_id": test_contact.id,
            "note": faker.text(max_nb_chars=500),
            "interaction_timestamp": datetime.now(timezone.utc),
            "action": "Follow up in 3 days",
            "action_timestamp": datetime.now(timezone.utc) + timedelta(days=3),
            "created_by_id": test_user.id,
        }

        near_interaction = ContactInteraction(**interaction_data_3_days)
        db.add(near_interaction)
        db.commit()
        db.refresh(near_interaction)

        response = client.get("/stats")
        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        stats = data["data"]

        assert stats["total_contacts"] == 1
        assert len(stats["upcoming_interactions"]) == 1
        interaction = stats["upcoming_interactions"][0]
        assert interaction["id"] == str(near_interaction.id)

        # Verify contact information is included
        assert "contact" in interaction
        assert interaction["contact"]["id"] == str(test_contact.id)

    def test_get_stats_includes_interactions_within_5_days(
        self, client, db, test_contact, faker, test_user
    ):
        """Test GET /stats endpoint includes interactions within 5 days."""
        interactions = []
        # Create interactions at different time points within 5 days
        for days in [1, 2, 3, 4, 5]:
            interaction_data = {
                "contact_id": test_contact.id,
                "note": faker.text(max_nb_chars=500),
                "interaction_timestamp": datetime.now(timezone.utc),
                "action": f"Follow up in {days} days",
                "action_timestamp": datetime.now(timezone.utc) + timedelta(days=days),
                "created_by_id": test_user.id,
            }

            interaction = ContactInteraction(**interaction_data)
            db.add(interaction)
            interactions.append(interaction)

        db.commit()
        for interaction in interactions:
            db.refresh(interaction)

        response = client.get("/stats")
        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        stats = data["data"]

        assert stats["total_contacts"] == 1
        assert len(stats["upcoming_interactions"]) == 5

        # Verify interactions are sorted by action_timestamp ascending
        action_timestamps = [
            datetime.fromisoformat(
                interaction["action_timestamp"].replace("Z", "+00:00")
            )
            for interaction in stats["upcoming_interactions"]
        ]
        assert action_timestamps == sorted(action_timestamps)

        # Verify all interactions have contact information
        for interaction in stats["upcoming_interactions"]:
            assert "contact" in interaction
            assert interaction["contact"]["id"] == str(test_contact.id)
            assert "first_name" in interaction["contact"]
            assert "last_name" in interaction["contact"]
            assert "email" in interaction["contact"]

    def test_get_stats_excludes_interactions_without_action(
        self, client, test_contact, test_contact_interaction
    ):
        """Test GET /stats endpoint excludes interactions without actions."""
        response = client.get("/stats")
        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        stats = data["data"]

        assert stats["total_contacts"] == 1
        assert len(stats["upcoming_interactions"]) == 0

    def test_get_stats_excludes_interactions_without_action_timestamp(
        self, client, test_contact, interaction_with_no_action_timestamp
    ):
        """Test GET /stats endpoint excludes interactions without action_timestamp."""
        response = client.get("/stats")
        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        stats = data["data"]

        assert stats["total_contacts"] == 1
        assert len(stats["upcoming_interactions"]) == 0

    def test_get_stats_comprehensive(
        self,
        client,
        db,
        test_contact,
        setup_contact,
        test_contact_list,
        public_contact_list,
        faker,
        test_user,
    ):
        """Test GET /stats endpoint with comprehensive data."""
        # Create additional private list
        private_list = ContactList(
            name=faker.company(),
            description=faker.text(max_nb_chars=200),
            created_by_id=test_user.id,
            is_public=False,
        )
        db.add(private_list)
        db.commit()
        db.refresh(private_list)

        # Create interactions: one within 5 days, one beyond 5 days
        interaction_within_5_days = ContactInteraction(
            contact_id=test_contact.id,
            note=faker.text(max_nb_chars=500),
            interaction_timestamp=datetime.now(timezone.utc),
            action="Follow up in 2 days",
            action_timestamp=datetime.now(timezone.utc) + timedelta(days=2),
            created_by_id=test_user.id,
        )
        db.add(interaction_within_5_days)

        interaction_beyond_5_days = ContactInteraction(
            contact_id=test_contact.id,
            note=faker.text(max_nb_chars=500),
            interaction_timestamp=datetime.now(timezone.utc),
            action="Follow up in 7 days",
            action_timestamp=datetime.now(timezone.utc) + timedelta(days=7),
            created_by_id=test_user.id,
        )
        db.add(interaction_beyond_5_days)
        db.commit()
        db.refresh(interaction_within_5_days)
        db.refresh(interaction_beyond_5_days)

        response = client.get("/stats")
        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        stats = data["data"]

        # Verify counts
        assert stats["total_contacts"] == 2
        assert (
            stats["total_list"] == 3
        )  # test_contact_list, public_contact_list, private_list
        assert stats["total_public_list"] == 1  # only public_contact_list
        assert stats["total_private_list"] == 2  # test_contact_list and private_list

        # Verify upcoming interactions (only the one within 5 days)
        assert len(stats["upcoming_interactions"]) == 1
        interaction = stats["upcoming_interactions"][0]
        assert interaction["id"] == str(interaction_within_5_days.id)

        # Verify contact information is included
        assert "contact" in interaction
        assert interaction["contact"]["id"] == str(test_contact.id)
        assert interaction["contact"]["first_name"] == test_contact.first_name
        assert interaction["contact"]["last_name"] == test_contact.last_name
        assert interaction["contact"]["email"] == test_contact.email

        # Verify recent_contacts includes the 2 contacts
        assert len(stats["recent_contacts"]) == 2
        recent_contact_ids = [c["id"] for c in stats["recent_contacts"]]
        assert str(test_contact.id) in recent_contact_ids
        assert str(setup_contact.id) in recent_contact_ids

        # Verify recent_contacts structure
        for contact in stats["recent_contacts"]:
            assert "id" in contact
            assert "first_name" in contact
            assert "last_name" in contact
            assert "email" in contact
            assert "created_at" in contact
            assert "updated_at" in contact

    def test_get_stats_recent_contacts_limit(self, client, db, faker, test_user):
        """Test GET /stats endpoint returns only last 5 contacts."""
        # Create 7 contacts
        contacts = []
        for i in range(7):
            contact = Contact(
                first_name=faker.first_name(),
                last_name=faker.last_name(),
                email=faker.email(),
                contact_type="personal",
                phone_type="mobile",
                created_by_id=test_user.id,
            )
            db.add(contact)
            contacts.append(contact)

        db.commit()
        for contact in contacts:
            db.refresh(contact)

        response = client.get("/stats")
        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        stats = data["data"]

        # Should only return last 5 contacts
        assert len(stats["recent_contacts"]) == 5

        # Verify they are the most recent ones (sorted by created_at descending)
        # The last 5 contacts created should be in the list
        last_5_contact_ids = {str(c.id) for c in contacts[-5:]}
        returned_contact_ids = {c["id"] for c in stats["recent_contacts"]}
        assert returned_contact_ids == last_5_contact_ids

        # Verify structure
        for contact in stats["recent_contacts"]:
            assert "id" in contact
            assert "first_name" in contact
            assert "last_name" in contact
            assert "email" in contact
            assert "created_at" in contact
            assert "updated_at" in contact

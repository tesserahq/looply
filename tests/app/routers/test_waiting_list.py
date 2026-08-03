from uuid import uuid4
from fastapi.testclient import TestClient


def test_list_member_statuses(client_test_user: TestClient):
    """Test getting all available member statuses for waiting lists."""
    response = client_test_user.get("/waiting-lists/member-statuses")
    if response.status_code != 200:
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
    assert response.status_code == 200

    data = response.json()
    assert "items" in data
    assert "size" in data
    assert "page" in data
    assert "pages" in data
    assert "total" in data
    assert data["page"] == 1
    assert data["pages"] == 1
    assert data["size"] == data["total"]

    # Verify structure of items
    assert isinstance(data["items"], list)
    assert len(data["items"]) > 0

    # Verify each item has the required fields
    for item in data["items"]:
        assert "value" in item
        assert "label" in item
        assert "description" in item
        assert isinstance(item["value"], str)
        assert isinstance(item["label"], str)
        assert isinstance(item["description"], str)

    # Verify specific statuses exist
    status_values = [item["value"] for item in data["items"]]
    assert "pending" in status_values
    assert "approved" in status_values
    assert "rejected" in status_values
    assert "notified" in status_values
    assert "active" in status_values


def test_list_member_statuses_structure(client_test_user: TestClient):
    """Test the structure of the member statuses response."""
    response = client_test_user.get("/waiting-lists/member-statuses")
    assert response.status_code == 200

    data = response.json()

    # Check pagination-like structure
    assert isinstance(data["items"], list)
    assert isinstance(data["size"], int)
    assert isinstance(data["page"], int)
    assert isinstance(data["pages"], int)
    assert isinstance(data["total"], int)

    # Check values match
    assert data["size"] == len(data["items"])
    assert data["total"] == len(data["items"])
    assert data["size"] == data["total"]


def test_create_waiting_list(client_test_user: TestClient, faker):
    """Test creating a waiting list."""
    waiting_list_data = {
        "name": faker.company(),
        "description": faker.text(max_nb_chars=200),
    }

    response = client_test_user.post("/waiting-lists", json=waiting_list_data)
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == waiting_list_data["name"]
    assert data["description"] == waiting_list_data["description"]
    assert data["id"] is not None


def test_create_waiting_list_minimal(client_test_user: TestClient, faker):
    """Test creating a waiting list with minimal data."""
    waiting_list_data = {"name": faker.company()}

    response = client_test_user.post("/waiting-lists", json=waiting_list_data)
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == waiting_list_data["name"]
    assert data["description"] is None
    assert data["id"] is not None


class TestWaitingListMembers:
    """Test class for POST /waiting-lists/{waiting_list_id}/members."""

    def test_add_members_by_contact_id(
        self, client_test_user: TestClient, test_waiting_list, test_contact
    ):
        """Test adding a member using an existing contact_id."""
        response = client_test_user.post(
            f"/waiting-lists/{test_waiting_list.id}/members",
            json={"contact_ids": [str(test_contact.id)]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["added_count"] == 1
        assert data["requested_count"] == 1

    def test_add_member_by_email_creates_contact(
        self, client_test_user: TestClient, test_waiting_list, faker, db
    ):
        """Test that a new contact is created when the email doesn't match one."""
        from app.models.contact import Contact

        email = faker.unique.email()
        response = client_test_user.post(
            f"/waiting-lists/{test_waiting_list.id}/members",
            json={
                "contacts": [
                    {"email": email, "first_name": "Emi", "last_name": "Jankowski"}
                ]
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["added_count"] == 1
        assert data["requested_count"] == 1

        created_contact = (
            db.query(Contact).filter(Contact.email == email.lower()).first()
        )
        assert created_contact is not None
        assert created_contact.first_name == "Emi"

    def test_add_member_by_email_reuses_existing_contact(
        self, client_test_user: TestClient, test_waiting_list, test_contact, db
    ):
        """Test that an existing contact is reused (not duplicated) by email."""
        from app.models.contact import Contact

        response = client_test_user.post(
            f"/waiting-lists/{test_waiting_list.id}/members",
            json={
                "contacts": [
                    {
                        "email": test_contact.email,
                        "first_name": "Someone Else",
                    }
                ]
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["added_count"] == 1

        matching_contacts = (
            db.query(Contact).filter(Contact.email == test_contact.email).all()
        )
        assert len(matching_contacts) == 1
        # Existing contact's name is untouched by the request payload.
        assert matching_contacts[0].first_name == test_contact.first_name

    def test_add_member_by_email_case_insensitive_match(
        self, client_test_user: TestClient, test_waiting_list, test_contact, db
    ):
        """Test that email matching is case-insensitive and doesn't create a duplicate."""
        from app.models.contact import Contact

        response = client_test_user.post(
            f"/waiting-lists/{test_waiting_list.id}/members",
            json={"contacts": [{"email": test_contact.email.upper()}]},
        )

        assert response.status_code == 200
        matching_contacts = (
            db.query(Contact).filter(Contact.email == test_contact.email).all()
        )
        assert len(matching_contacts) == 1

    def test_add_members_mixed_ids_and_emails(
        self, client_test_user: TestClient, test_waiting_list, test_contact, faker
    ):
        """Test that contact_ids and contacts can be combined in one request."""
        response = client_test_user.post(
            f"/waiting-lists/{test_waiting_list.id}/members",
            json={
                "contact_ids": [str(test_contact.id)],
                "contacts": [{"email": faker.unique.email()}],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["added_count"] == 2
        assert data["requested_count"] == 2

    def test_add_members_empty_request(
        self, client_test_user: TestClient, test_waiting_list
    ):
        """Test that an empty request (no contact_ids, no contacts) is rejected."""
        response = client_test_user.post(
            f"/waiting-lists/{test_waiting_list.id}/members", json={}
        )
        assert response.status_code == 400

    def test_add_members_waiting_list_not_found(self, client_test_user: TestClient):
        """Test adding members to a non-existent waiting list."""
        fake_id = str(uuid4())
        response = client_test_user.post(
            f"/waiting-lists/{fake_id}/members",
            json={"contacts": [{"email": "someone@example.com"}]},
        )
        assert response.status_code == 404

    def test_re_add_member_by_contact_id_after_removal(
        self, client_test_user: TestClient, test_waiting_list, test_contact
    ):
        """Re-adding a previously removed member by contact_id should succeed, not 500."""
        add_response = client_test_user.post(
            f"/waiting-lists/{test_waiting_list.id}/members",
            json={"contact_ids": [str(test_contact.id)]},
        )
        assert add_response.status_code == 200

        remove_response = client_test_user.delete(
            f"/waiting-lists/{test_waiting_list.id}/members/{test_contact.id}"
        )
        assert remove_response.status_code == 204

        re_add_response = client_test_user.post(
            f"/waiting-lists/{test_waiting_list.id}/members",
            json={"contact_ids": [str(test_contact.id)]},
        )

        assert re_add_response.status_code == 200
        assert re_add_response.json()["added_count"] == 1

    def test_re_add_member_by_email_after_removal(
        self, client_test_user: TestClient, test_waiting_list, test_contact
    ):
        """Re-adding a previously removed member by email should succeed, not 500."""
        add_response = client_test_user.post(
            f"/waiting-lists/{test_waiting_list.id}/members",
            json={"contacts": [{"email": test_contact.email}]},
        )
        assert add_response.status_code == 200

        remove_response = client_test_user.delete(
            f"/waiting-lists/{test_waiting_list.id}/members/{test_contact.id}"
        )
        assert remove_response.status_code == 204

        re_add_response = client_test_user.post(
            f"/waiting-lists/{test_waiting_list.id}/members",
            json={"contacts": [{"email": test_contact.email}]},
        )

        assert re_add_response.status_code == 200
        assert re_add_response.json()["added_count"] == 1


class TestGetWaitingListMembers:
    """Test class for GET /waiting-lists/{waiting_list_id}/members."""

    def test_list_all_members(
        self, client_test_user: TestClient, test_waiting_list, test_contact, faker
    ):
        """Test listing all members when no email filter is provided."""
        other_email = faker.unique.email()
        client_test_user.post(
            f"/waiting-lists/{test_waiting_list.id}/members",
            json={
                "contact_ids": [str(test_contact.id)],
                "contacts": [{"email": other_email}],
            },
        )

        response = client_test_user.get(
            f"/waiting-lists/{test_waiting_list.id}/members"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["waiting_list_id"] == str(test_waiting_list.id)
        assert len(data["members"]) == 2

    def test_filter_members_by_email_match(
        self, client_test_user: TestClient, test_waiting_list, test_contact, faker
    ):
        """Test filtering members by email returns the matching member."""
        other_email = faker.unique.email()
        client_test_user.post(
            f"/waiting-lists/{test_waiting_list.id}/members",
            json={
                "contact_ids": [str(test_contact.id)],
                "contacts": [{"email": other_email}],
            },
        )

        response = client_test_user.get(
            f"/waiting-lists/{test_waiting_list.id}/members",
            params={"email": test_contact.email},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["members"]) == 1
        assert data["members"][0]["contact"]["email"] == test_contact.email
        assert data["members"][0]["contact_id"] == str(test_contact.id)

    def test_filter_members_by_email_no_match(
        self, client_test_user: TestClient, test_waiting_list, test_contact
    ):
        """Test filtering by an unknown email returns an empty members list."""
        client_test_user.post(
            f"/waiting-lists/{test_waiting_list.id}/members",
            json={"contact_ids": [str(test_contact.id)]},
        )

        response = client_test_user.get(
            f"/waiting-lists/{test_waiting_list.id}/members",
            params={"email": "not-on-list@example.com"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["members"] == []

    def test_filter_members_by_email_case_insensitive(
        self, client_test_user: TestClient, test_waiting_list, test_contact
    ):
        """Test that email filtering is case-insensitive."""
        client_test_user.post(
            f"/waiting-lists/{test_waiting_list.id}/members",
            json={"contact_ids": [str(test_contact.id)]},
        )

        response = client_test_user.get(
            f"/waiting-lists/{test_waiting_list.id}/members",
            params={"email": test_contact.email.upper()},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["members"]) == 1
        assert data["members"][0]["contact"]["email"] == test_contact.email

    def test_filter_members_waiting_list_not_found(self, client_test_user: TestClient):
        """Test filtering members on a non-existent waiting list returns 404."""
        fake_id = str(uuid4())
        response = client_test_user.get(
            f"/waiting-lists/{fake_id}/members",
            params={"email": "someone@example.com"},
        )
        assert response.status_code == 404

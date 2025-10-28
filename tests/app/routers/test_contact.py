from uuid import uuid4


class TestContactRouter:
    """Test class for contact router endpoints."""

    def test_create_contact(self, client, faker):
        """Test POST /contacts endpoint."""
        contact_data = {
            "first_name": faker.first_name(),
            "last_name": faker.last_name(),
            "company": faker.company(),
            "job": faker.job(),
            "contact_type": "business",
            "phone_type": "work",
            "phone": faker.phone_number(),
            "email": faker.email(),
            "website": faker.url(),
            "address_line_1": faker.street_address(),
            "city": faker.city(),
            "state": faker.state(),
            "zip_code": faker.zipcode(),
            "country": faker.country(),
            "notes": faker.text(max_nb_chars=200),
            "is_active": True,
            "created_by_id": str(client.app.state.test_user.id),
        }

        response = client.post("/contacts", json=contact_data)
        assert response.status_code == 201
        contact = response.json()
        assert contact["first_name"] == contact_data["first_name"]
        assert contact["last_name"] == contact_data["last_name"]
        assert contact["email"] == contact_data["email"]
        assert contact["created_by_id"] == contact_data["created_by_id"]

    def test_create_contact_minimal_data(self, client):
        """Test POST /contacts with minimal required data."""
        contact_data = {
            "contact_type": "personal",
            "phone_type": "mobile",
            "created_by_id": str(client.app.state.test_user.id),
        }

        response = client.post("/contacts", json=contact_data)
        assert response.status_code == 201
        contact = response.json()
        assert contact["contact_type"] == contact_data["contact_type"]
        assert contact["phone_type"] == contact_data["phone_type"]
        assert contact["created_by_id"] == contact_data["created_by_id"]

    def test_create_contact_duplicate_email(self, client, test_contact, faker):
        """Test POST /contacts with duplicate email fails."""
        contact_data = {
            "first_name": faker.first_name(),
            "last_name": faker.last_name(),
            "contact_type": "personal",
            "phone_type": "mobile",
            "email": test_contact.email,  # Same email as existing contact
            "created_by_id": str(client.app.state.test_user.id),
        }

        response = client.post("/contacts", json=contact_data)
        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]

    def test_create_contact_duplicate_phone(self, client, test_contact, faker):
        """Test POST /contacts with duplicate phone fails."""
        contact_data = {
            "first_name": faker.first_name(),
            "last_name": faker.last_name(),
            "contact_type": "personal",
            "phone_type": "mobile",
            "phone": test_contact.phone,  # Same phone as existing contact
            "created_by_id": str(client.app.state.test_user.id),
        }

        response = client.post("/contacts", json=contact_data)
        assert response.status_code == 400
        assert "Phone number already registered" in response.json()["detail"]

    def test_list_contacts_pagination(self, client, test_contact, setup_contact):
        """Test GET /contacts with pagination."""
        response = client.get("/contacts")
        assert response.status_code == 200

        data = response.json()
        # Check pagination structure
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "size" in data
        assert "pages" in data

        # Should have at least 2 contacts
        assert data["total"] >= 2
        assert len(data["items"]) >= 2

    def test_list_contacts_pagination_params(self, client, test_contact, setup_contact):
        """Test GET /contacts with pagination parameters."""
        response = client.get("/contacts?page=1&size=1")
        assert response.status_code == 200

        data = response.json()
        assert data["page"] == 1
        assert data["size"] == 1
        assert len(data["items"]) == 1

    def test_get_contact(self, client, test_contact):
        """Test GET /contacts/{contact_id} endpoint."""
        response = client.get(f"/contacts/{test_contact.id}")
        assert response.status_code == 200
        contact = response.json()
        assert contact["id"] == str(test_contact.id)
        assert contact["first_name"] == test_contact.first_name

    def test_get_contact_not_found(self, client):
        """Test GET /contacts/{contact_id} with non-existent ID."""
        fake_id = str(uuid4())
        response = client.get(f"/contacts/{fake_id}")
        assert response.status_code == 404
        assert "Contact not found" in response.json()["detail"]

    def test_update_contact(self, client, test_contact, faker):
        """Test PUT /contacts/{contact_id} endpoint."""
        update_data = {
            "first_name": "Updated First Name",
            "last_name": "Updated Last Name",
            "email": faker.email(),
        }

        response = client.put(f"/contacts/{test_contact.id}", json=update_data)
        assert response.status_code == 200
        contact = response.json()
        assert contact["first_name"] == update_data["first_name"]
        assert contact["last_name"] == update_data["last_name"]
        assert contact["email"] == update_data["email"]

    def test_update_contact_duplicate_email(
        self, client, test_contact, setup_contact, faker
    ):
        """Test PUT /contacts/{contact_id} with duplicate email fails."""
        update_data = {
            "email": setup_contact.email,  # Email from another contact
        }

        response = client.put(f"/contacts/{test_contact.id}", json=update_data)
        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]

    def test_update_contact_not_found(self, client, faker):
        """Test PUT /contacts/{contact_id} with non-existent ID."""
        fake_id = str(uuid4())
        update_data = {"first_name": "Updated Name"}

        response = client.put(f"/contacts/{fake_id}", json=update_data)
        assert response.status_code == 404
        assert "Contact not found" in response.json()["detail"]

    def test_delete_contact(self, client, test_contact):
        """Test DELETE /contacts/{contact_id} endpoint."""
        response = client.delete(f"/contacts/{test_contact.id}")
        assert response.status_code == 204

        # Verify contact is soft deleted
        get_response = client.get(f"/contacts/{test_contact.id}")
        assert get_response.status_code == 404

    def test_delete_contact_not_found(self, client):
        """Test DELETE /contacts/{contact_id} with non-existent ID."""
        fake_id = str(uuid4())
        response = client.delete(f"/contacts/{fake_id}")
        assert response.status_code == 404
        assert "Contact not found" in response.json()["detail"]


class TestContactRouterPagination:
    """Test class specifically for pagination functionality."""

    def test_pagination_default_params(self, client, test_contact, setup_contact):
        """Test pagination with default parameters."""
        response = client.get("/contacts")
        assert response.status_code == 200

        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "size" in data
        assert "pages" in data

        # Default page should be 1
        assert data["page"] == 1
        # Default size should be 50 (fastapi-pagination default)
        assert data["size"] == 50

    def test_pagination_custom_params(self, client, test_contact, setup_contact):
        """Test pagination with custom parameters."""
        response = client.get("/contacts?page=2&size=1")
        assert response.status_code == 200

        data = response.json()
        assert data["page"] == 2
        assert data["size"] == 1
        assert len(data["items"]) == 1

    def test_pagination_invalid_params(self, client, test_contact):
        """Test pagination with invalid parameters."""
        # Test negative page
        response = client.get("/contacts?page=-1")
        assert response.status_code == 422

        # Test zero size
        response = client.get("/contacts?size=0")
        assert response.status_code == 422

    def test_pagination_empty_result(self, client):
        """Test pagination with no results."""
        response = client.get("/contacts")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["size"] == 50
        assert data["pages"] == 0
        assert len(data["items"]) == 0

    def test_pagination_consistency_across_endpoints(
        self, client, test_contact, setup_contact
    ):
        """Test that pagination works consistently across all list endpoints."""
        endpoints = [
            "/contacts",
        ]

        for endpoint in endpoints:
            response = client.get(f"{endpoint}?page=1&size=1")
            assert response.status_code == 200

            data = response.json()
            assert "items" in data
            assert "total" in data
            assert "page" in data
            assert "size" in data
            assert data["page"] == 1
            assert data["size"] == 1


class TestContactRouterSearch:
    """Test class for contact search functionality."""

    def test_search_contacts(self, client, test_contact):
        """Test GET /contacts/search endpoint."""
        response = client.get("/contacts/search", params={"q": test_contact.first_name})
        assert response.status_code == 200

        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "size" in data
        assert "pages" in data
        assert len(data["items"]) >= 1
        # Verify the search result includes the expected contact
        contact_ids = [item["id"] for item in data["items"]]
        assert str(test_contact.id) in contact_ids

    def test_search_contacts_last_name(self, client, test_contact):
        """Test GET /contacts/search endpoint with last name."""
        response = client.get("/contacts/search", params={"q": test_contact.last_name})
        assert response.status_code == 200

        data = response.json()
        assert len(data["items"]) >= 1
        contact_ids = [item["id"] for item in data["items"]]
        assert str(test_contact.id) in contact_ids

    def test_search_contacts_email(self, client, test_contact):
        """Test GET /contacts/search endpoint with email."""
        if test_contact.email:
            response = client.get("/contacts/search", params={"q": test_contact.email})
            assert response.status_code == 200

            data = response.json()
            assert len(data["items"]) >= 1
            contact_ids = [item["id"] for item in data["items"]]
            assert str(test_contact.id) in contact_ids

    def test_search_contacts_company(self, client, test_contact):
        """Test GET /contacts/search endpoint with company."""
        if test_contact.company:
            response = client.get(
                "/contacts/search", params={"q": test_contact.company}
            )
            assert response.status_code == 200

            data = response.json()
            assert len(data["items"]) >= 1
            contact_ids = [item["id"] for item in data["items"]]
            assert str(test_contact.id) in contact_ids

    def test_search_contacts_no_results(self, client):
        """Test GET /contacts/search with no matches."""
        response = client.get(
            "/contacts/search", params={"q": "nonexistentsearchterm12345"}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0

    def test_search_contacts_missing_query(self, client):
        """Test GET /contacts/search without query parameter."""
        response = client.get("/contacts/search")
        # FastAPI will return 422 (unprocessable entity) for missing required parameter
        assert response.status_code == 422

    def test_search_contacts_empty_query(self, client):
        """Test GET /contacts/search with empty query."""
        response = client.get("/contacts/search", params={"q": ""})
        assert response.status_code == 400
        assert "required" in response.json()["detail"].lower()

    def test_search_contacts_pagination(self, client, test_contact, setup_contact):
        """Test GET /contacts/search with pagination."""
        response = client.get(
            "/contacts/search",
            params={"q": test_contact.first_name, "page": 1, "size": 1},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["page"] == 1
        assert data["size"] == 1
        assert len(data["items"]) <= 1

    def test_search_contacts_case_insensitive(self, client, test_contact):
        """Test that search is case insensitive."""
        # Search with lowercase
        response_lower = client.get(
            "/contacts/search", params={"q": test_contact.first_name.lower()}
        )
        assert response_lower.status_code == 200

        # Search with uppercase
        response_upper = client.get(
            "/contacts/search", params={"q": test_contact.first_name.upper()}
        )
        assert response_upper.status_code == 200

        # Both should return the same results
        data_lower = response_lower.json()
        data_upper = response_upper.json()
        assert data_lower["total"] == data_upper["total"]

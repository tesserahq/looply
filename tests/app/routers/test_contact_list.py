import pytest
from uuid import uuid4
from fastapi.testclient import TestClient


def test_create_contact_list(client_test_user: TestClient, faker):
    """Test creating a contact list."""
    contact_list_data = {
        "name": faker.company(),
        "description": faker.text(max_nb_chars=200),
    }

    response = client_test_user.post("/contact-lists", json=contact_list_data)
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == contact_list_data["name"]
    assert data["description"] == contact_list_data["description"]
    assert data["id"] is not None


def test_create_contact_list_minimal(client_test_user: TestClient, faker):
    """Test creating a contact list with minimal data."""
    contact_list_data = {
        "name": faker.company(),
    }

    response = client_test_user.post("/contact-lists", json=contact_list_data)
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == contact_list_data["name"]
    assert data["description"] is None


def test_list_contact_lists(client_test_user: TestClient, test_contact_list, faker):
    """Test listing contact lists."""
    response = client_test_user.get("/contact-lists")
    assert response.status_code == 200

    data = response.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) > 0


def test_get_contact_list(client_test_user: TestClient, test_contact_list):
    """Test getting a contact list by ID."""
    response = client_test_user.get(f"/contact-lists/{test_contact_list.id}")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == str(test_contact_list.id)
    assert data["name"] == test_contact_list.name
    assert data["description"] == test_contact_list.description


def test_get_contact_list_not_found(client_test_user: TestClient):
    """Test getting a non-existent contact list."""
    non_existent_id = uuid4()
    response = client_test_user.get(f"/contact-lists/{non_existent_id}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_update_contact_list(client_test_user: TestClient, test_contact_list, faker):
    """Test updating a contact list."""
    update_data = {
        "name": faker.company(),
        "description": faker.text(max_nb_chars=100),
    }

    response = client_test_user.put(
        f"/contact-lists/{test_contact_list.id}", json=update_data
    )
    assert response.status_code == 200

    data = response.json()
    assert data["name"] == update_data["name"]
    assert data["description"] == update_data["description"]
    assert data["id"] == str(test_contact_list.id)


def test_update_contact_list_partial(client_test_user: TestClient, test_contact_list):
    """Test updating a contact list with partial data."""
    update_data = {"name": "Updated Name Only"}

    response = client_test_user.put(
        f"/contact-lists/{test_contact_list.id}", json=update_data
    )
    assert response.status_code == 200

    data = response.json()
    assert data["name"] == update_data["name"]
    # Description should remain unchanged
    assert data["description"] == test_contact_list.description


def test_update_contact_list_not_found(client_test_user: TestClient):
    """Test updating a non-existent contact list."""
    non_existent_id = uuid4()
    update_data = {"name": "Updated Name"}

    response = client_test_user.put(
        f"/contact-lists/{non_existent_id}", json=update_data
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_delete_contact_list(client_test_user: TestClient, test_contact_list):
    """Test deleting a contact list."""
    response = client_test_user.delete(f"/contact-lists/{test_contact_list.id}")
    assert response.status_code == 204

    # Verify it's deleted (should return 404)
    get_response = client_test_user.get(f"/contact-lists/{test_contact_list.id}")
    assert get_response.status_code == 404


def test_delete_contact_list_not_found(client_test_user: TestClient):
    """Test deleting a non-existent contact list."""
    non_existent_id = uuid4()
    response = client_test_user.delete(f"/contact-lists/{non_existent_id}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_search_contact_lists(client_test_user: TestClient, test_contact_list):
    """Test searching contact lists with filters."""
    # Search by exact name match
    filters = {"name": test_contact_list.name}
    response = client_test_user.post("/contact-lists/search", json=filters)
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert any(item["id"] == str(test_contact_list.id) for item in data)


def test_search_contact_lists_by_partial_name(
    client_test_user: TestClient, test_contact_list
):
    """Test searching contact lists with partial name match."""
    filters = {
        "name": {"operator": "ilike", "value": f"%{test_contact_list.name[:5]}%"}
    }
    response = client_test_user.post("/contact-lists/search", json=filters)
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert any(item["id"] == str(test_contact_list.id) for item in data)


def test_search_contact_lists_no_results(client_test_user: TestClient):
    """Test searching contact lists with filters that return no results."""
    filters = {
        "name": {"operator": "==", "value": "nonexistent_contact_list_name_12345"}
    }
    response = client_test_user.post("/contact-lists/search", json=filters)
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_create_and_list_multiple_contact_lists(client_test_user: TestClient, faker):
    """Test creating multiple contact lists and listing them."""
    # Create multiple contact lists
    created_ids = []
    for i in range(5):
        contact_list_data = {
            "name": f"{faker.company()} {i}",
            "description": faker.text(max_nb_chars=100),
        }
        response = client_test_user.post("/contact-lists", json=contact_list_data)
        assert response.status_code == 201
        created_ids.append(response.json()["id"])

    # List all contact lists
    response = client_test_user.get("/contact-lists")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) >= 5

    # Verify all created contact lists are present
    item_ids = [item["id"] for item in data["items"]]
    for created_id in created_ids:
        assert created_id in item_ids

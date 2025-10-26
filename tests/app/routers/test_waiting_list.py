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

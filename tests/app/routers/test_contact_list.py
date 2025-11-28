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


def test_list_public_contact_lists(
    client_test_user: TestClient, public_contact_list, test_contact_list
):
    """Test listing only public contact lists."""
    response = client_test_user.get("/contact-lists/public")
    assert response.status_code == 200

    data = response.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) > 0

    # Verify all returned lists are public
    for item in data["items"]:
        assert item["is_public"] is True

    # Verify the public contact list is included
    item_ids = [item["id"] for item in data["items"]]
    assert str(public_contact_list.id) in item_ids

    # Verify the private contact list is NOT included
    assert str(test_contact_list.id) not in item_ids


def test_list_public_contact_lists_empty(client_test_user: TestClient):
    """Test listing public contact lists when none exist."""
    response = client_test_user.get("/contact-lists/public")
    assert response.status_code == 200

    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 0
    assert len(data["items"]) == 0


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


def test_get_my_subscriptions_empty(client_test_user: TestClient):
    """Test getting my subscriptions when user has no subscriptions."""
    response = client_test_user.get("/contact-lists/subscriptions")
    assert response.status_code == 200

    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) == 0
    assert data["page"] == 1
    assert data["total"] == 0


def test_get_my_subscriptions_with_subscriptions(
    client_test_user: TestClient, public_contact_list, db, test_user
):
    """Test getting my subscriptions when user is subscribed to public lists."""
    from app.commands.contact_list.subscribe_user_command import SubscribeUserCommand
    from app.schemas.user import User

    # Subscribe user to public contact list
    command = SubscribeUserCommand(db)
    user_schema = User.model_validate(test_user)
    command.execute(public_contact_list.id, user_schema)

    # Get my subscriptions
    response = client_test_user.get("/contact-lists/subscriptions")
    assert response.status_code == 200

    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == str(public_contact_list.id)
    # Verify created_by_id and is_public are not in the response
    assert "created_by_id" not in data["items"][0]
    assert "is_public" not in data["items"][0]


def test_get_my_subscriptions_only_public_lists(
    client_test_user: TestClient, public_contact_list, test_contact_list, db, test_user
):
    """Test that subscriptions only returns public lists, not private ones."""
    from app.commands.contact_list.subscribe_user_command import SubscribeUserCommand
    from app.services.contact_list_service import ContactListService
    from app.services.contact_service import ContactService
    from app.schemas.user import User

    # Subscribe user to public contact list
    subscribe_command = SubscribeUserCommand(db)
    user_schema = User.model_validate(test_user)
    subscribe_command.execute(public_contact_list.id, user_schema)

    # Add user's contact to private contact list (not via subscription)
    contact_service = ContactService(db)
    contact = contact_service.get_contact_by_email(test_user.email)
    assert contact is not None

    contact_list_service = ContactListService(db)
    contact_list_service.add_contact_to_list(test_contact_list.id, contact.id)

    # Get my subscriptions - should only return public list
    response = client_test_user.get("/contact-lists/subscriptions")
    assert response.status_code == 200

    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == str(public_contact_list.id)
    # Verify created_by_id and is_public are not in the response
    assert "created_by_id" not in data["items"][0]
    assert "is_public" not in data["items"][0]

    # Verify private list is not included
    list_ids = [item["id"] for item in data["items"]]
    assert str(test_contact_list.id) not in list_ids


def test_get_my_subscriptions_multiple_public_lists(
    client_test_user: TestClient, db, test_user, faker
):
    """Test getting my subscriptions with multiple public lists."""
    from app.models.contact_list import ContactList
    from app.commands.contact_list.subscribe_user_command import SubscribeUserCommand
    from app.schemas.user import User

    # Create multiple public contact lists
    public_list1 = ContactList(
        name=faker.company(),
        description=faker.text(max_nb_chars=100),
        is_public=True,
        created_by_id=test_user.id,
    )
    db.add(public_list1)
    db.commit()
    db.refresh(public_list1)

    public_list2 = ContactList(
        name=faker.company(),
        description=faker.text(max_nb_chars=100),
        is_public=True,
        created_by_id=test_user.id,
    )
    db.add(public_list2)
    db.commit()
    db.refresh(public_list2)

    # Subscribe user to both public lists
    subscribe_command = SubscribeUserCommand(db)
    user_schema = User.model_validate(test_user)
    subscribe_command.execute(public_list1.id, user_schema)
    subscribe_command.execute(public_list2.id, user_schema)

    # Get my subscriptions
    response = client_test_user.get("/contact-lists/subscriptions")
    assert response.status_code == 200

    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) == 2

    # Verify both lists are included
    list_ids = [item["id"] for item in data["items"]]
    assert str(public_list1.id) in list_ids
    assert str(public_list2.id) in list_ids

    # Verify created_by_id and is_public are not in the response
    for item in data["items"]:
        assert "created_by_id" not in item
        assert "is_public" not in item

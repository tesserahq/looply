from uuid import uuid4
from fastapi.testclient import TestClient


def test_add_members_to_list(
    client_test_user: TestClient, test_contact_list, test_contact, faker
):
    """Test adding members to a contact list."""
    request_data = {"contact_ids": [str(test_contact.id)]}

    response = client_test_user.post(
        f"/contact-lists/{test_contact_list.id}/members", json=request_data
    )

    assert response.status_code == 200
    data = response.json()
    assert data["added_count"] == 1
    assert data["requested_count"] == 1


def test_add_duplicate_member_returns_422(
    client_test_user: TestClient, test_contact_list, test_contact
):
    """Adding the same contact twice should return a 422 response."""
    request_data = {"contact_ids": [str(test_contact.id)]}

    first_response = client_test_user.post(
        f"/contact-lists/{test_contact_list.id}/members", json=request_data
    )
    assert first_response.status_code == 200

    duplicate_response = client_test_user.post(
        f"/contact-lists/{test_contact_list.id}/members", json=request_data
    )

    assert duplicate_response.status_code == 422
    assert "already a member" in duplicate_response.json()["detail"]


def test_add_multiple_members_to_list(
    client_test_user: TestClient, test_contact_list, test_contact, faker, test_user, db
):
    """Test adding multiple members to a contact list."""
    from app.models.contact import Contact

    # Create additional contacts
    contact2 = Contact(
        first_name=faker.first_name(),
        last_name=faker.last_name(),
        contact_type="business",
        phone_type="work",
        phone=faker.phone_number(),
        email=faker.email(),
        created_by_id=test_user.id,
    )
    contact3 = Contact(
        first_name=faker.first_name(),
        last_name=faker.last_name(),
        contact_type="business",
        phone_type="work",
        phone=faker.phone_number(),
        email=faker.email(),
        created_by_id=test_user.id,
    )

    db.add_all([contact2, contact3])
    db.commit()
    db.refresh(contact2)
    db.refresh(contact3)

    request_data = {
        "contact_ids": [str(test_contact.id), str(contact2.id), str(contact3.id)]
    }

    response = client_test_user.post(
        f"/contact-lists/{test_contact_list.id}/members", json=request_data
    )

    assert response.status_code == 200
    data = response.json()
    assert data["added_count"] == 3


def test_add_members_to_nonexistent_list(client_test_user: TestClient, test_contact):
    """Test adding members to a non-existent list."""
    nonexistent_list_id = uuid4()
    request_data = {"contact_ids": [str(test_contact.id)]}

    response = client_test_user.post(
        f"/contact-lists/{nonexistent_list_id}/members", json=request_data
    )

    assert response.status_code == 404


def test_remove_member_from_list(
    client_test_user: TestClient, test_contact_list, test_contact
):
    """Test removing a member from a contact list."""
    # First add the contact
    request_data = {"contact_ids": [str(test_contact.id)]}
    client_test_user.post(
        f"/contact-lists/{test_contact_list.id}/members", json=request_data
    )

    # Then remove it
    response = client_test_user.delete(
        f"/contact-lists/{test_contact_list.id}/members/{test_contact.id}"
    )

    assert response.status_code == 204


def test_remove_nonexistent_member(client_test_user: TestClient, test_contact_list):
    """Test removing a member that doesn't exist in the list."""
    nonexistent_contact_id = uuid4()
    response = client_test_user.delete(
        f"/contact-lists/{test_contact_list.id}/members/{nonexistent_contact_id}"
    )

    assert response.status_code == 404


def test_get_list_members(
    client_test_user: TestClient, test_contact_list, test_contact, faker, test_user, db
):
    """Test getting all members of a contact list."""
    from app.models.contact import Contact

    # Create another contact
    contact2 = Contact(
        first_name=faker.first_name(),
        last_name=faker.last_name(),
        contact_type="business",
        phone_type="work",
        phone=faker.phone_number(),
        email=faker.email(),
        created_by_id=test_user.id,
    )

    db.add(contact2)
    db.commit()
    db.refresh(contact2)

    # Add contacts to list
    request_data = {"contact_ids": [str(test_contact.id), str(contact2.id)]}
    client_test_user.post(
        f"/contact-lists/{test_contact_list.id}/members", json=request_data
    )

    # Get members
    response = client_test_user.get(f"/contact-lists/{test_contact_list.id}/members")
    assert response.status_code == 200

    data = response.json()
    assert data["contact_list_id"] == str(test_contact_list.id)
    assert len(data["members"]) == 2


def test_get_list_members_empty(client_test_user: TestClient, test_contact_list):
    """Test getting members from an empty list."""
    response = client_test_user.get(f"/contact-lists/{test_contact_list.id}/members")
    assert response.status_code == 200

    data = response.json()
    assert data["contact_list_id"] == str(test_contact_list.id)
    assert len(data["members"]) == 0


def test_get_list_members_nonexistent_list(client_test_user: TestClient):
    """Test getting members from a non-existent list."""
    nonexistent_list_id = uuid4()
    response = client_test_user.get(f"/contact-lists/{nonexistent_list_id}/members")
    assert response.status_code == 404


def test_get_list_member_count(
    client_test_user: TestClient, test_contact_list, test_contact, faker, test_user, db
):
    """Test getting member count of a contact list."""
    # Initially should be 0
    response = client_test_user.get(
        f"/contact-lists/{test_contact_list.id}/members/count"
    )
    assert response.status_code == 200

    data = response.json()
    assert data["contact_list_id"] == str(test_contact_list.id)
    assert data["count"] == 0

    # Add a contact
    from app.models.contact import Contact

    contact2 = Contact(
        first_name=faker.first_name(),
        last_name=faker.last_name(),
        contact_type="business",
        phone_type="work",
        phone=faker.phone_number(),
        email=faker.email(),
        created_by_id=test_user.id,
    )

    db.add(contact2)
    db.commit()
    db.refresh(contact2)

    request_data = {"contact_ids": [str(test_contact.id), str(contact2.id)]}
    client_test_user.post(
        f"/contact-lists/{test_contact_list.id}/members", json=request_data
    )

    # Check count
    response = client_test_user.get(
        f"/contact-lists/{test_contact_list.id}/members/count"
    )
    assert response.status_code == 200

    data = response.json()
    assert data["count"] == 2


def test_clear_list_members(
    client_test_user: TestClient, test_contact_list, test_contact, faker, test_user, db
):
    """Test clearing all members from a list."""
    from app.models.contact import Contact

    # Create additional contacts
    contact2 = Contact(
        first_name=faker.first_name(),
        last_name=faker.last_name(),
        contact_type="business",
        phone_type="work",
        phone=faker.phone_number(),
        email=faker.email(),
        created_by_id=test_user.id,
    )

    db.add(contact2)
    db.commit()
    db.refresh(contact2)

    # Add contacts
    request_data = {"contact_ids": [str(test_contact.id), str(contact2.id)]}
    client_test_user.post(
        f"/contact-lists/{test_contact_list.id}/members", json=request_data
    )

    # Clear all
    response = client_test_user.delete(f"/contact-lists/{test_contact_list.id}/members")
    assert response.status_code == 200

    data = response.json()
    assert data["removed_count"] == 2

    # Verify list is empty
    get_response = client_test_user.get(
        f"/contact-lists/{test_contact_list.id}/members"
    )
    assert len(get_response.json()["members"]) == 0


def test_get_contact_lists_for_contact(
    client_test_user: TestClient, test_contact_list, test_contact, faker, test_user, db
):
    """Test getting all contact lists for a contact."""
    from app.models.contact_list import ContactList

    # Create another list
    another_list = ContactList(
        name=faker.company(),
        description=faker.text(max_nb_chars=100),
        created_by_id=test_user.id,
    )

    db.add(another_list)
    db.commit()
    db.refresh(another_list)

    # Add contact to both lists
    request_data = {"contact_ids": [str(test_contact.id)]}
    client_test_user.post(
        f"/contact-lists/{test_contact_list.id}/members", json=request_data
    )
    client_test_user.post(
        f"/contact-lists/{another_list.id}/members", json=request_data
    )

    # Get lists for contact
    response = client_test_user.get(
        f"/contact-lists/contacts/{test_contact.id}/contact-lists"
    )
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2
    list_ids = [contact_list["id"] for contact_list in data]
    assert str(test_contact_list.id) in list_ids
    assert str(another_list.id) in list_ids


def test_get_contact_lists_for_nonexistent_contact(client_test_user: TestClient):
    """Test getting lists for a non-existent contact."""
    nonexistent_contact_id = uuid4()
    response = client_test_user.get(
        f"/contact-lists/contacts/{nonexistent_contact_id}/contact-lists"
    )
    assert response.status_code == 404


def test_check_contact_membership(
    client_test_user: TestClient, test_contact_list, test_contact
):
    """Test checking if a contact is a member of a list."""
    # Initially not a member
    response = client_test_user.get(
        f"/contact-lists/{test_contact_list.id}/members/{test_contact.id}/is-member"
    )
    assert response.status_code == 200

    data = response.json()
    assert data["is_member"] is False

    # Add to list
    request_data = {"contact_ids": [str(test_contact.id)]}
    client_test_user.post(
        f"/contact-lists/{test_contact_list.id}/members", json=request_data
    )

    # Check again
    response = client_test_user.get(
        f"/contact-lists/{test_contact_list.id}/members/{test_contact.id}/is-member"
    )
    assert response.status_code == 200

    data = response.json()
    assert data["is_member"] is True


def test_check_membership_nonexistent_list(client_test_user: TestClient, test_contact):
    """Test checking membership for a non-existent list."""
    nonexistent_list_id = uuid4()
    response = client_test_user.get(
        f"/contact-lists/{nonexistent_list_id}/members/{test_contact.id}/is-member"
    )
    assert response.status_code == 404

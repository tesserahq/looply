from uuid import uuid4


def test_create_event_field_mapping(client_test_user, test_custom_field_definition):
    payload = {
        "event_type": "com.mylinden.person.created",
        "source_path": "account.family_member_count",
        "field_name": test_custom_field_definition.name,
    }

    response = client_test_user.post("/event-field-mappings", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["event_type"] == payload["event_type"]
    assert data["source_path"] == payload["source_path"]
    assert data["field_definition_id"] == str(test_custom_field_definition.id)
    assert data["field_name"] == test_custom_field_definition.name
    assert data["created_by_id"] is not None


def test_create_event_field_mapping_undefined_field(client_test_user):
    payload = {
        "event_type": "com.mylinden.person.created",
        "source_path": "account.family_member_count",
        "field_name": "does-not-exist",
    }

    response = client_test_user.post("/event-field-mappings", json=payload)
    assert response.status_code == 422


def test_list_event_field_mappings(client_test_user, test_event_field_mapping):
    response = client_test_user.get("/event-field-mappings")
    assert response.status_code == 200

    ids = [item["id"] for item in response.json()["items"]]
    assert str(test_event_field_mapping.id) in ids


def test_get_event_field_mapping(client_test_user, test_event_field_mapping):
    response = client_test_user.get(
        f"/event-field-mappings/{test_event_field_mapping.id}"
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(test_event_field_mapping.id)


def test_get_event_field_mapping_not_found(client_test_user):
    response = client_test_user.get(f"/event-field-mappings/{uuid4()}")
    assert response.status_code == 404


def test_delete_event_field_mapping(client_test_user, test_event_field_mapping):
    response = client_test_user.delete(
        f"/event-field-mappings/{test_event_field_mapping.id}"
    )
    assert response.status_code == 204

    list_response = client_test_user.get("/event-field-mappings")
    ids = [item["id"] for item in list_response.json()["items"]]
    assert str(test_event_field_mapping.id) not in ids


def test_delete_event_field_mapping_not_found(client_test_user):
    response = client_test_user.delete(f"/event-field-mappings/{uuid4()}")
    assert response.status_code == 404

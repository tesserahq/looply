from uuid import uuid4


def test_create_custom_field_definition(client_test_user, faker):
    payload = {"name": faker.unique.slug(), "value_type": "string", "label": "Label"}

    response = client_test_user.post("/custom-field-definitions", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == payload["name"]
    assert data["value_type"] == "string"
    assert data["label"] == "Label"
    assert data["created_by_id"] is not None


def test_create_custom_field_definition_invalid_value_type(client_test_user, faker):
    payload = {"name": faker.unique.slug(), "value_type": "not_a_real_type"}

    response = client_test_user.post("/custom-field-definitions", json=payload)
    assert response.status_code == 422


def test_create_custom_field_definition_duplicate_name_conflict(
    client_test_user, faker
):
    name = faker.unique.slug()
    client_test_user.post(
        "/custom-field-definitions", json={"name": name, "value_type": "string"}
    )

    response = client_test_user.post(
        "/custom-field-definitions", json={"name": name, "value_type": "number"}
    )
    assert response.status_code == 409


def test_list_custom_field_definitions(client_test_user, test_custom_field_definition):
    response = client_test_user.get("/custom-field-definitions")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] >= 1
    ids = [item["id"] for item in data["items"]]
    assert str(test_custom_field_definition.id) in ids


def test_get_custom_field_definition(client_test_user, test_custom_field_definition):
    response = client_test_user.get(
        f"/custom-field-definitions/{test_custom_field_definition.id}"
    )
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == str(test_custom_field_definition.id)
    assert data["name"] == test_custom_field_definition.name


def test_get_custom_field_definition_not_found(client_test_user):
    response = client_test_user.get(f"/custom-field-definitions/{uuid4()}")
    assert response.status_code == 404


def test_update_custom_field_definition_label(
    client_test_user, test_custom_field_definition
):
    response = client_test_user.put(
        f"/custom-field-definitions/{test_custom_field_definition.id}",
        json={"label": "New Label"},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["label"] == "New Label"
    assert data["name"] == test_custom_field_definition.name
    assert data["value_type"] == test_custom_field_definition.value_type


def test_update_custom_field_definition_not_found(client_test_user):
    response = client_test_user.put(
        f"/custom-field-definitions/{uuid4()}", json={"label": "New Label"}
    )
    assert response.status_code == 404


def test_delete_custom_field_definition(client_test_user, test_custom_field_definition):
    response = client_test_user.delete(
        f"/custom-field-definitions/{test_custom_field_definition.id}"
    )
    assert response.status_code == 204

    list_response = client_test_user.get("/custom-field-definitions")
    ids = [item["id"] for item in list_response.json()["items"]]
    assert str(test_custom_field_definition.id) not in ids


def test_delete_custom_field_definition_not_found(client_test_user):
    response = client_test_user.delete(f"/custom-field-definitions/{uuid4()}")
    assert response.status_code == 404


def test_delete_then_recreate_same_name(client_test_user, faker):
    name = faker.unique.slug()
    create_response = client_test_user.post(
        "/custom-field-definitions", json={"name": name, "value_type": "string"}
    )
    definition_id = create_response.json()["id"]

    client_test_user.delete(f"/custom-field-definitions/{definition_id}")

    recreate_response = client_test_user.post(
        "/custom-field-definitions", json={"name": name, "value_type": "number"}
    )
    assert recreate_response.status_code == 201
    assert recreate_response.json()["id"] != definition_id

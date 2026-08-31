def _create_contact_with_external_id(client_test_user, faker, external_id=None):
    external_id = external_id or faker.unique.uuid4()
    response = client_test_user.post(
        "/contacts",
        json={
            "external_id": external_id,
            "contact_type": "personal",
            "phone_type": "mobile",
            "created_by_id": str(client_test_user.app.state.test_user.id),
        },
    )
    assert response.status_code == 201
    return response.json(), external_id


def test_set_contact_custom_field_value(
    client_test_user, faker, test_custom_field_definition
):
    contact, external_id = _create_contact_with_external_id(client_test_user, faker)

    response = client_test_user.put(
        f"/contacts/{external_id}/custom-fields/{test_custom_field_definition.name}",
        json={"value": "hello"},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["value"] == "hello"
    assert data["field_name"] == test_custom_field_definition.name
    assert data["set_by_user_id"] == str(client_test_user.app.state.test_user.id)


def test_set_contact_custom_field_value_overwrites(
    client_test_user, faker, test_custom_field_definition
):
    contact, external_id = _create_contact_with_external_id(client_test_user, faker)
    path = f"/contacts/{external_id}/custom-fields/{test_custom_field_definition.name}"

    client_test_user.put(path, json={"value": "hello"})
    response = client_test_user.put(path, json={"value": "goodbye"})
    assert response.status_code == 200
    assert response.json()["value"] == "goodbye"

    list_response = client_test_user.get(f"/contacts/{external_id}/custom-fields")
    assert len(list_response.json()) == 1


def test_set_contact_custom_field_value_undefined_field(client_test_user, faker):
    contact, external_id = _create_contact_with_external_id(client_test_user, faker)

    response = client_test_user.put(
        f"/contacts/{external_id}/custom-fields/does_not_exist",
        json={"value": "hello"},
    )
    assert response.status_code == 422


def test_set_contact_custom_field_value_type_mismatch(
    client_test_user, faker, test_custom_field_definition
):
    """test_custom_field_definition is STRING - a number must be rejected."""
    contact, external_id = _create_contact_with_external_id(client_test_user, faker)

    response = client_test_user.put(
        f"/contacts/{external_id}/custom-fields/{test_custom_field_definition.name}",
        json={"value": 3},
    )
    assert response.status_code == 422


def test_set_contact_custom_field_value_unknown_external_id(
    client_test_user, faker, test_custom_field_definition
):
    response = client_test_user.put(
        f"/contacts/{faker.unique.uuid4()}/custom-fields/{test_custom_field_definition.name}",
        json={"value": "hello"},
    )
    assert response.status_code == 404


def test_list_contact_custom_field_values(
    client_test_user, faker, test_custom_field_definition
):
    contact, external_id = _create_contact_with_external_id(client_test_user, faker)
    client_test_user.put(
        f"/contacts/{external_id}/custom-fields/{test_custom_field_definition.name}",
        json={"value": "hello"},
    )

    response = client_test_user.get(f"/contacts/{external_id}/custom-fields")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["field_name"] == test_custom_field_definition.name


def test_delete_contact_custom_field_value(
    client_test_user, faker, test_custom_field_definition
):
    contact, external_id = _create_contact_with_external_id(client_test_user, faker)
    client_test_user.put(
        f"/contacts/{external_id}/custom-fields/{test_custom_field_definition.name}",
        json={"value": "hello"},
    )

    response = client_test_user.delete(
        f"/contacts/{external_id}/custom-fields/{test_custom_field_definition.name}"
    )
    assert response.status_code == 204

    list_response = client_test_user.get(f"/contacts/{external_id}/custom-fields")
    assert list_response.json() == []


def test_delete_contact_custom_field_value_not_found(
    client_test_user, faker, test_custom_field_definition
):
    contact, external_id = _create_contact_with_external_id(client_test_user, faker)

    response = client_test_user.delete(
        f"/contacts/{external_id}/custom-fields/{test_custom_field_definition.name}"
    )
    assert response.status_code == 404

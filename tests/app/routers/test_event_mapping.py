from uuid import uuid4


def test_create_event_mapping(client_test_user, faker):
    payload = {"event_type": f"com.mylinden.{faker.unique.slug()}"}

    response = client_test_user.post("/event-mappings", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["event_type"] == payload["event_type"]
    assert data["created_by_id"] is not None
    assert data["identity_target_field"] is None


def test_create_event_mapping_with_identity(client_test_user, faker):
    payload = {
        "event_type": f"com.mylinden.{faker.unique.slug()}",
        "identity_target_field": "external_id",
        "identity_source_path": "person.id",
    }

    response = client_test_user.post("/event-mappings", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["identity_target_field"] == "external_id"
    assert data["identity_source_path"] == "person.id"


def test_create_event_mapping_identity_fields_must_be_set_together(
    client_test_user, faker
):
    payload = {
        "event_type": f"com.mylinden.{faker.unique.slug()}",
        "identity_target_field": "external_id",
    }

    response = client_test_user.post("/event-mappings", json=payload)
    assert response.status_code == 422


def test_create_event_mapping_duplicate_conflict(client_test_user, faker):
    event_type = f"com.mylinden.{faker.unique.slug()}"
    client_test_user.post("/event-mappings", json={"event_type": event_type})

    response = client_test_user.post("/event-mappings", json={"event_type": event_type})
    assert response.status_code == 409


def test_list_event_mappings(client_test_user, test_event_mapping):
    response = client_test_user.get("/event-mappings")
    assert response.status_code == 200

    ids = [item["id"] for item in response.json()["items"]]
    assert str(test_event_mapping.id) in ids


def test_get_event_mapping(client_test_user, test_event_mapping):
    response = client_test_user.get(f"/event-mappings/{test_event_mapping.id}")
    assert response.status_code == 200
    assert response.json()["id"] == str(test_event_mapping.id)


def test_get_event_mapping_not_found(client_test_user):
    response = client_test_user.get(f"/event-mappings/{uuid4()}")
    assert response.status_code == 404


def test_update_event_mapping_identity(client_test_user, test_event_mapping):
    payload = {"identity_target_field": "email", "identity_source_path": "person.email"}

    response = client_test_user.patch(
        f"/event-mappings/{test_event_mapping.id}", json=payload
    )
    assert response.status_code == 200
    assert response.json()["identity_target_field"] == "email"
    assert response.json()["identity_source_path"] == "person.email"


def test_update_event_mapping_invalid_identity_target_field(
    client_test_user, test_event_mapping
):
    payload = {"identity_target_field": "city", "identity_source_path": "person.city"}

    response = client_test_user.patch(
        f"/event-mappings/{test_event_mapping.id}", json=payload
    )
    assert response.status_code == 422


def test_clone_event_mapping(client_test_user, test_identity_event_mapping, faker):
    new_event_type = f"com.mylinden.{faker.unique.slug()}"

    response = client_test_user.post(
        f"/event-mappings/{test_identity_event_mapping.id}/clone",
        json={"event_type": new_event_type},
    )
    assert response.status_code == 201

    data = response.json()
    assert data["id"] != str(test_identity_event_mapping.id)
    assert data["event_type"] == new_event_type
    assert (
        data["identity_target_field"]
        == test_identity_event_mapping.identity_target_field
    )
    assert (
        data["identity_source_path"] == test_identity_event_mapping.identity_source_path
    )
    assert data["created_by_id"] is not None

    fields_response = client_test_user.get(f"/event-mappings/{data['id']}/fields")
    assert fields_response.json()["total"] == 0


def test_clone_event_mapping_deep_copies_field_mappings(
    client_test_user, test_event_mapping, test_event_field_mapping, faker
):
    new_event_type = f"com.mylinden.{faker.unique.slug()}"

    response = client_test_user.post(
        f"/event-mappings/{test_event_mapping.id}/clone",
        json={"event_type": new_event_type},
    )
    clone_id = response.json()["id"]

    fields_response = client_test_user.get(f"/event-mappings/{clone_id}/fields")
    items = fields_response.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] != str(test_event_field_mapping.id)
    assert items[0]["source_path"] == test_event_field_mapping.source_path


def test_clone_event_mapping_duplicate_conflict(client_test_user, test_event_mapping):
    response = client_test_user.post(
        f"/event-mappings/{test_event_mapping.id}/clone",
        json={"event_type": test_event_mapping.event_type},
    )
    assert response.status_code == 409


def test_clone_event_mapping_not_found(client_test_user, faker):
    response = client_test_user.post(
        f"/event-mappings/{uuid4()}/clone",
        json={"event_type": f"com.mylinden.{faker.unique.slug()}"},
    )
    assert response.status_code == 404


def test_delete_event_mapping(client_test_user, test_event_mapping):
    response = client_test_user.delete(f"/event-mappings/{test_event_mapping.id}")
    assert response.status_code == 204

    list_response = client_test_user.get("/event-mappings")
    ids = [item["id"] for item in list_response.json()["items"]]
    assert str(test_event_mapping.id) not in ids


def test_delete_event_mapping_not_found(client_test_user):
    response = client_test_user.delete(f"/event-mappings/{uuid4()}")
    assert response.status_code == 404


def test_delete_then_recreate_same_event_type(client_test_user, faker):
    event_type = f"com.mylinden.{faker.unique.slug()}"
    create_response = client_test_user.post(
        "/event-mappings", json={"event_type": event_type}
    )
    event_mapping_id = create_response.json()["id"]

    client_test_user.delete(f"/event-mappings/{event_mapping_id}")

    recreate_response = client_test_user.post(
        "/event-mappings", json={"event_type": event_type}
    )
    assert recreate_response.status_code == 201
    assert recreate_response.json()["id"] != event_mapping_id


def test_delete_event_mapping_cascades_to_field_mappings(
    client_test_user, test_event_mapping, test_event_field_mapping
):
    response = client_test_user.delete(f"/event-mappings/{test_event_mapping.id}")
    assert response.status_code == 204

    get_response = client_test_user.get(
        f"/event-mappings/{test_event_mapping.id}/fields/{test_event_field_mapping.id}"
    )
    assert get_response.status_code == 404


# --- nested /fields sub-resource ---


def test_create_event_field_mapping(
    client_test_user, test_event_mapping, test_custom_field_definition
):
    payload = {
        "source_path": "account.family_member_count",
        "field_name": test_custom_field_definition.name,
    }

    response = client_test_user.post(
        f"/event-mappings/{test_event_mapping.id}/fields", json=payload
    )
    assert response.status_code == 201

    data = response.json()
    assert data["event_mapping_id"] == str(test_event_mapping.id)
    assert data["source_path"] == payload["source_path"]
    assert data["field_definition_id"] == str(test_custom_field_definition.id)
    assert data["field_name"] == test_custom_field_definition.name
    assert data["created_by_id"] is not None


def test_create_event_field_mapping_undefined_field(
    client_test_user, test_event_mapping
):
    payload = {
        "source_path": "account.family_member_count",
        "field_name": "does-not-exist",
    }

    response = client_test_user.post(
        f"/event-mappings/{test_event_mapping.id}/fields", json=payload
    )
    assert response.status_code == 422


def test_create_event_field_mapping_parent_not_found(client_test_user):
    payload = {"source_path": "a", "field_name": "does-not-matter"}

    response = client_test_user.post(f"/event-mappings/{uuid4()}/fields", json=payload)
    assert response.status_code == 404


def test_list_event_field_mappings(
    client_test_user, test_event_mapping, test_event_field_mapping
):
    response = client_test_user.get(f"/event-mappings/{test_event_mapping.id}/fields")
    assert response.status_code == 200

    ids = [item["id"] for item in response.json()["items"]]
    assert str(test_event_field_mapping.id) in ids


def test_get_event_field_mapping(
    client_test_user, test_event_mapping, test_event_field_mapping
):
    response = client_test_user.get(
        f"/event-mappings/{test_event_mapping.id}/fields/{test_event_field_mapping.id}"
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(test_event_field_mapping.id)


def test_get_event_field_mapping_not_found(client_test_user, test_event_mapping):
    response = client_test_user.get(
        f"/event-mappings/{test_event_mapping.id}/fields/{uuid4()}"
    )
    assert response.status_code == 404


def test_get_event_field_mapping_wrong_parent_is_404(
    client_test_user, test_event_mapping, test_event_field_mapping, faker
):
    other = client_test_user.post(
        "/event-mappings", json={"event_type": f"com.mylinden.{faker.unique.slug()}"}
    )
    other_id = other.json()["id"]

    response = client_test_user.get(
        f"/event-mappings/{other_id}/fields/{test_event_field_mapping.id}"
    )
    assert response.status_code == 404


def test_update_event_field_mapping_source_path(
    client_test_user, test_event_mapping, test_event_field_mapping
):
    response = client_test_user.patch(
        f"/event-mappings/{test_event_mapping.id}/fields/{test_event_field_mapping.id}",
        json={"source_path": "account.new_path"},
    )
    assert response.status_code == 200
    assert response.json()["source_path"] == "account.new_path"


def test_update_event_field_mapping_switch_to_contact_field(
    client_test_user, test_event_mapping, test_event_field_mapping
):
    response = client_test_user.patch(
        f"/event-mappings/{test_event_mapping.id}/fields/{test_event_field_mapping.id}",
        json={"target_type": "contact_field", "target_field": "city"},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["target_type"] == "contact_field"
    assert data["target_field"] == "city"
    assert data["field_definition_id"] is None


def test_update_event_field_mapping_switch_to_contact_field_without_target_field_rejected(
    client_test_user, test_event_mapping, test_event_field_mapping
):
    response = client_test_user.patch(
        f"/event-mappings/{test_event_mapping.id}/fields/{test_event_field_mapping.id}",
        json={"target_type": "contact_field"},
    )
    assert response.status_code == 422


def test_update_event_field_mapping_unrecognized_target_field_rejected(
    client_test_user, test_event_mapping
):
    create_response = client_test_user.post(
        f"/event-mappings/{test_event_mapping.id}/fields",
        json={
            "source_path": "person.first_name",
            "target_type": "contact_field",
            "target_field": "first_name",
        },
    )
    mapping_id = create_response.json()["id"]

    response = client_test_user.patch(
        f"/event-mappings/{test_event_mapping.id}/fields/{mapping_id}",
        json={"target_field": "not_a_real_column"},
    )
    assert response.status_code == 422


def test_delete_event_field_mapping(
    client_test_user, test_event_mapping, test_event_field_mapping
):
    response = client_test_user.delete(
        f"/event-mappings/{test_event_mapping.id}/fields/{test_event_field_mapping.id}"
    )
    assert response.status_code == 204

    list_response = client_test_user.get(
        f"/event-mappings/{test_event_mapping.id}/fields"
    )
    ids = [item["id"] for item in list_response.json()["items"]]
    assert str(test_event_field_mapping.id) not in ids


def test_delete_event_field_mapping_not_found(client_test_user, test_event_mapping):
    response = client_test_user.delete(
        f"/event-mappings/{test_event_mapping.id}/fields/{uuid4()}"
    )
    assert response.status_code == 404


def test_create_contact_field_mapping(client_test_user, test_event_mapping):
    payload = {
        "source_path": "person.first_name",
        "target_type": "contact_field",
        "target_field": "first_name",
    }

    response = client_test_user.post(
        f"/event-mappings/{test_event_mapping.id}/fields", json=payload
    )
    assert response.status_code == 201

    data = response.json()
    assert data["target_type"] == "contact_field"
    assert data["target_field"] == "first_name"
    assert data["field_definition_id"] is None
    assert data["field_name"] is None


def test_create_contact_field_mapping_unrecognized_target_field(
    client_test_user, test_event_mapping
):
    payload = {
        "source_path": "person.something",
        "target_type": "contact_field",
        "target_field": "not_a_real_column",
    }

    response = client_test_user.post(
        f"/event-mappings/{test_event_mapping.id}/fields", json=payload
    )
    assert response.status_code == 422

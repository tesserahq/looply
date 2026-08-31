from uuid import uuid4


def test_create_tracked_event_type(client_test_user, faker):
    payload = {"event_type": f"com.mylinden.{faker.unique.slug()}"}

    response = client_test_user.post("/tracked-event-types", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["event_type"] == payload["event_type"]
    assert data["created_by_id"] is not None


def test_create_tracked_event_type_duplicate_conflict(client_test_user, faker):
    event_type = f"com.mylinden.{faker.unique.slug()}"
    client_test_user.post("/tracked-event-types", json={"event_type": event_type})

    response = client_test_user.post(
        "/tracked-event-types", json={"event_type": event_type}
    )
    assert response.status_code == 409


def test_list_tracked_event_types(client_test_user, test_tracked_event_type):
    response = client_test_user.get("/tracked-event-types")
    assert response.status_code == 200

    ids = [item["id"] for item in response.json()["items"]]
    assert str(test_tracked_event_type.id) in ids


def test_get_tracked_event_type(client_test_user, test_tracked_event_type):
    response = client_test_user.get(
        f"/tracked-event-types/{test_tracked_event_type.id}"
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(test_tracked_event_type.id)


def test_get_tracked_event_type_not_found(client_test_user):
    response = client_test_user.get(f"/tracked-event-types/{uuid4()}")
    assert response.status_code == 404


def test_delete_tracked_event_type(client_test_user, test_tracked_event_type):
    response = client_test_user.delete(
        f"/tracked-event-types/{test_tracked_event_type.id}"
    )
    assert response.status_code == 204

    list_response = client_test_user.get("/tracked-event-types")
    ids = [item["id"] for item in list_response.json()["items"]]
    assert str(test_tracked_event_type.id) not in ids


def test_delete_tracked_event_type_not_found(client_test_user):
    response = client_test_user.delete(f"/tracked-event-types/{uuid4()}")
    assert response.status_code == 404


def test_delete_then_recreate_same_event_type(client_test_user, faker):
    event_type = f"com.mylinden.{faker.unique.slug()}"
    create_response = client_test_user.post(
        "/tracked-event-types", json={"event_type": event_type}
    )
    tracked_id = create_response.json()["id"]

    client_test_user.delete(f"/tracked-event-types/{tracked_id}")

    recreate_response = client_test_user.post(
        "/tracked-event-types", json={"event_type": event_type}
    )
    assert recreate_response.status_code == 201
    assert recreate_response.json()["id"] != tracked_id

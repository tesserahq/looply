from uuid import uuid4

from fastapi.testclient import TestClient


def _list_membership_payload(list_id):
    return {"root": {"type": "list_membership", "list_id": str(list_id), "op": "in"}}


def test_create_segment(client_test_user: TestClient, faker, test_contact_list):
    payload = {
        "name": faker.catch_phrase(),
        "rule": _list_membership_payload(test_contact_list.id),
    }

    response = client_test_user.post("/segments", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == payload["name"]
    assert data["rule"]["root"]["list_id"] == str(test_contact_list.id)


def test_create_segment_invalid_rule_tree_returns_422(client_test_user: TestClient, faker):
    payload = {
        "name": faker.catch_phrase(),
        "rule": {"root": {"type": "not_a_real_type"}},
    }

    response = client_test_user.post("/segments", json=payload)
    assert response.status_code == 422


def test_create_segment_dangling_campaign_reference_returns_422(
    client_test_user: TestClient, faker
):
    payload = {
        "name": faker.catch_phrase(),
        "rule": {
            "root": {
                "type": "campaign_activity",
                "campaign_id": str(uuid4()),
                "event": "opened",
                "op": "has_not",
            }
        },
    }

    response = client_test_user.post("/segments", json=payload)
    assert response.status_code == 422


def test_create_segment_duplicate_name_returns_409(
    client_test_user: TestClient, faker, test_contact_list, test_segment
):
    payload = {
        "name": test_segment.name,
        "rule": _list_membership_payload(test_contact_list.id),
    }

    response = client_test_user.post("/segments", json=payload)
    assert response.status_code == 409


def test_list_segments(client_test_user: TestClient, test_segment):
    response = client_test_user.get("/segments")
    assert response.status_code == 200
    assert len(response.json()["items"]) > 0


def test_get_segment(client_test_user: TestClient, test_segment):
    response = client_test_user.get(f"/segments/{test_segment.id}")
    assert response.status_code == 200
    assert response.json()["id"] == str(test_segment.id)


def test_get_segment_not_found(client_test_user: TestClient):
    response = client_test_user.get(f"/segments/{uuid4()}")
    assert response.status_code == 404


def test_update_segment(client_test_user: TestClient, test_segment, faker):
    new_name = faker.catch_phrase()
    response = client_test_user.put(f"/segments/{test_segment.id}", json={"name": new_name})
    assert response.status_code == 200
    assert response.json()["name"] == new_name


def test_delete_segment(client_test_user: TestClient, test_segment):
    response = client_test_user.delete(f"/segments/{test_segment.id}")
    assert response.status_code == 204
    assert client_test_user.get(f"/segments/{test_segment.id}").status_code == 404


def test_preview_saved_segment(
    client_test_user: TestClient, test_segment, test_contact_list, test_contact, db
):
    from app.repositories.contact_list_repository import ContactListRepository

    ContactListRepository(db).add_contact_to_list(test_contact_list.id, test_contact.id)

    response = client_test_user.get(f"/segments/{test_segment.id}/preview")
    assert response.status_code == 200
    assert response.json()["contact_count"] == 1


def test_preview_draft_segment(client_test_user: TestClient, test_contact_list, test_contact, db):
    from app.repositories.contact_list_repository import ContactListRepository

    ContactListRepository(db).add_contact_to_list(test_contact_list.id, test_contact.id)

    response = client_test_user.post(
        "/segments/preview", json=_list_membership_payload(test_contact_list.id)
    )
    assert response.status_code == 200
    assert response.json()["contact_count"] == 1


def test_preview_draft_segment_dangling_campaign_returns_422(client_test_user: TestClient):
    response = client_test_user.post(
        "/segments/preview",
        json={
            "root": {
                "type": "campaign_activity",
                "campaign_id": str(uuid4()),
                "event": "opened",
                "op": "has_not",
            }
        },
    )
    assert response.status_code == 422

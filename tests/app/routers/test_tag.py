from uuid import uuid4


def test_create_tag(client_test_user, faker):
    response = client_test_user.post("/tags", json={"name": "VIP"})
    assert response.status_code == 201
    assert response.json()["name"] == "VIP"


def test_create_duplicate_tag_conflict(client_test_user):
    client_test_user.post("/tags", json={"name": "vip"})
    response = client_test_user.post("/tags", json={"name": "VIP"})
    assert response.status_code == 409


def test_update_tag_rename(client_test_user):
    created = client_test_user.post("/tags", json={"name": "vip"}).json()
    response = client_test_user.put(
        f"/tags/{created['id']}", json={"name": "VIP Customer"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "VIP Customer"


def test_delete_tag(client_test_user):
    created = client_test_user.post("/tags", json={"name": "vip"}).json()
    response = client_test_user.delete(f"/tags/{created['id']}")
    assert response.status_code == 204
    assert client_test_user.get(f"/tags/{created['id']}").status_code == 404


def test_get_tag_not_found(client_test_user):
    assert client_test_user.get(f"/tags/{uuid4()}").status_code == 404


def test_list_tags_includes_usage_counts(client_test_user, faker):
    client_test_user.post("/tags", json={"name": "vip"})
    client_test_user.post(
        "/contacts",
        json={
            "first_name": faker.first_name(),
            "contact_type": "lead",
            "phone_type": "mobile",
            "tags": ["vip"],
        },
    )

    response = client_test_user.get("/tags")

    assert response.status_code == 200
    vip = next(t for t in response.json()["items"] if t["name"] == "vip")
    assert vip["contacts_count"] == 1
    assert vip["campaigns_count"] == 0


def test_tag_usage_lists_referencing_segments(client_test_user):
    tag = client_test_user.post("/tags", json={"name": "vip"}).json()
    segment = client_test_user.post(
        "/segments",
        json={
            "name": "VIP segment",
            "rule": {"root": {"type": "tags", "tag_ids": [tag["id"]], "op": "in"}},
        },
    ).json()

    response = client_test_user.get(f"/tags/{tag['id']}/usage")

    assert response.status_code == 200
    body = response.json()
    assert body["contacts_count"] == 0
    assert [s["id"] for s in body["segments"]] == [segment["id"]]


def test_create_contact_with_tags_auto_creates_them(client_test_user, faker):
    payload = {
        "first_name": faker.first_name(),
        "contact_type": "lead",
        "phone_type": "mobile",
        "tags": ["vip", "newsletter"],
    }
    response = client_test_user.post("/contacts", json=payload)
    assert response.status_code == 201
    assert set(response.json()["tags"]) == {"vip", "newsletter"}


def test_update_contact_replaces_tags(client_test_user, faker):
    contact = client_test_user.post(
        "/contacts",
        json={
            "first_name": faker.first_name(),
            "contact_type": "lead",
            "phone_type": "mobile",
            "tags": ["vip", "newsletter"],
        },
    ).json()

    response = client_test_user.put(
        f"/contacts/{contact['id']}", json={"tags": ["newsletter"]}
    )
    assert response.status_code == 200
    assert response.json()["tags"] == ["newsletter"]


def test_list_contacts_filtered_by_tag(client_test_user, faker):
    tagged = client_test_user.post(
        "/contacts",
        json={
            "first_name": faker.first_name(),
            "contact_type": "lead",
            "phone_type": "mobile",
            "tags": ["vip"],
        },
    ).json()
    client_test_user.post(
        "/contacts",
        json={
            "first_name": faker.first_name(),
            "contact_type": "lead",
            "phone_type": "mobile",
            "tags": [],
        },
    )

    response = client_test_user.get("/contacts", params={"tags": "vip"})
    assert response.status_code == 200
    ids = [c["id"] for c in response.json()["items"]]
    assert ids == [tagged["id"]]


def test_create_campaign_with_tags_auto_creates_them(
    client_test_user, faker, test_segment
):
    response = client_test_user.post(
        "/campaigns",
        json={
            "name": faker.catch_phrase(),
            "segment_id": str(test_segment.id),
            "tags": ["newsletter"],
        },
    )
    assert response.status_code == 201
    assert response.json()["tags"] == ["newsletter"]

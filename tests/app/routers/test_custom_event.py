def test_list_custom_events_global(client_test_user, test_custom_event):
    response = client_test_user.get("/custom-events")
    assert response.status_code == 200

    ids = [item["id"] for item in response.json()["items"]]
    assert str(test_custom_event.id) in ids


def test_list_custom_events_filter_by_name(client_test_user, test_custom_event):
    response = client_test_user.get(
        "/custom-events", params={"name": test_custom_event.name}
    )
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["items"]]
    assert str(test_custom_event.id) in ids

    response = client_test_user.get("/custom-events", params={"name": "no.such.event"})
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_list_custom_events_filter_by_contact_id(
    client_test_user, test_custom_event, test_contact
):
    response = client_test_user.get(
        "/custom-events", params={"contact_id": str(test_contact.id)}
    )
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["items"]]
    assert str(test_custom_event.id) in ids


def test_list_custom_events_includes_raw_envelope(client_test_user, test_custom_event):
    response = client_test_user.get("/custom-events")
    item = next(
        item
        for item in response.json()["items"]
        if item["id"] == str(test_custom_event.id)
    )
    assert item["raw_envelope"] == test_custom_event.raw_envelope


def test_get_custom_event(client_test_user, test_custom_event):
    response = client_test_user.get(f"/custom-events/{test_custom_event.id}")
    assert response.status_code == 200
    assert response.json()["id"] == str(test_custom_event.id)
    assert response.json()["raw_envelope"] == test_custom_event.raw_envelope


def test_get_custom_event_not_found(client_test_user):
    from uuid import uuid4

    response = client_test_user.get(f"/custom-events/{uuid4()}")
    assert response.status_code == 404


def test_list_contact_custom_events(
    client_test_user, db, test_contact, test_custom_event
):
    test_contact.external_id = "contact-ext-id"
    db.commit()

    response = client_test_user.get(
        f"/contacts/{test_contact.external_id}/custom-events"
    )
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == str(test_custom_event.id)


def test_list_contact_custom_events_filters_by_name(
    client_test_user, db, test_contact, test_custom_event
):
    test_contact.external_id = "contact-ext-id"
    db.commit()

    response = client_test_user.get(
        f"/contacts/{test_contact.external_id}/custom-events",
        params={"name": "no.such.event"},
    )
    assert response.status_code == 200
    assert response.json() == []


def test_list_contact_custom_events_unknown_external_id(client_test_user):
    response = client_test_user.get("/contacts/no-such-external-id/custom-events")
    assert response.status_code == 404

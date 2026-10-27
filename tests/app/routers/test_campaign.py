from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient
from tessera_sdk.clients.sendly import (
    CreateEmailResponse,
    RenderResponse,
    SendBroadcastResponse,
)

from app.constants.campaign import CampaignStatus
from app.repositories.contact_list_repository import ContactListRepository
from app.routers.campaign import contact_rbac


def test_create_campaign(client_test_user: TestClient, faker, test_segment):
    payload = {
        "name": faker.catch_phrase(),
        "segment_id": str(test_segment.id),
        "html": "<p>Hi ${first_name}</p>",
        "layout_id": str(uuid4()),
        "subject": "Hello",
        "from_email": "news@example.com",
    }

    response = client_test_user.post("/campaigns", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == payload["name"]
    assert data["status"] == CampaignStatus.DRAFT.value
    assert data["id"] is not None
    assert data["html"] == payload["html"]
    assert data["layout_id"] == payload["layout_id"]


def test_update_draft_campaign_content(client_test_user: TestClient, draft_campaign):
    new_layout_id = str(uuid4())
    response = client_test_user.put(
        f"/campaigns/{draft_campaign.id}",
        json={"html": "<p>Updated</p>", "layout_id": new_layout_id},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["html"] == "<p>Updated</p>"
    assert data["layout_id"] == new_layout_id
    # Fields not sent are left alone.
    assert data["subject"] == draft_campaign.subject


def test_create_campaign_invalid_segment_returns_404(
    client_test_user: TestClient, faker
):
    payload = {
        "name": faker.catch_phrase(),
        "segment_id": str(uuid4()),
    }

    response = client_test_user.post("/campaigns", json=payload)
    assert response.status_code == 404


def test_list_campaigns(client_test_user: TestClient, draft_campaign):
    response = client_test_user.get("/campaigns")
    assert response.status_code == 200

    data = response.json()
    assert "items" in data
    assert len(data["items"]) > 0


def test_get_campaign(client_test_user: TestClient, draft_campaign):
    response = client_test_user.get(f"/campaigns/{draft_campaign.id}")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == str(draft_campaign.id)


def test_get_campaign_not_found(client_test_user: TestClient):
    response = client_test_user.get(f"/campaigns/{uuid4()}")
    assert response.status_code == 404


def test_update_draft_campaign(client_test_user: TestClient, draft_campaign, faker):
    original_name = draft_campaign.name
    new_name = faker.catch_phrase()
    response = client_test_user.put(
        f"/campaigns/{draft_campaign.id}", json={"name": new_name}
    )
    assert response.status_code == 200
    assert response.json()["name"] == new_name
    assert response.json()["name"] != original_name


def test_update_non_draft_campaign_blocked(
    client_test_user: TestClient, sending_campaign, faker
):
    response = client_test_user.put(
        f"/campaigns/{sending_campaign.id}", json={"name": faker.catch_phrase()}
    )
    assert response.status_code == 400


def test_delete_campaign(client_test_user: TestClient, draft_campaign):
    response = client_test_user.delete(f"/campaigns/{draft_campaign.id}")
    assert response.status_code == 204

    assert client_test_user.get(f"/campaigns/{draft_campaign.id}").status_code == 404


def test_send_campaign_success(
    client_test_user: TestClient,
    draft_campaign,
    test_contact_list,
    test_contact,
    db,
    monkeypatch,
):
    ContactListRepository(db).add_contact_to_list(test_contact_list.id, test_contact.id)

    class FakeSendlyClient:
        def send_broadcast(self, request):
            return SendBroadcastResponse(
                batch_id="batch-router-test", queued_count=1, suppressed_count=0
            )

    monkeypatch.setattr(
        "app.commands.campaign.send_campaign_command.build_sendly_client",
        lambda: FakeSendlyClient(),
    )

    response = client_test_user.post(f"/campaigns/{draft_campaign.id}/send")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == CampaignStatus.SENDING.value
    assert data["batch_id"] == "batch-router-test"
    assert data["recipient_count"] == 1


def test_send_campaign_not_found(client_test_user: TestClient):
    response = client_test_user.post(f"/campaigns/{uuid4()}/send")
    assert response.status_code == 404


def test_send_campaign_no_recipients_returns_400(
    client_test_user: TestClient, draft_campaign, monkeypatch
):
    monkeypatch.setattr(
        "app.commands.campaign.send_campaign_command.build_sendly_client",
        lambda: object(),
    )

    response = client_test_user.post(f"/campaigns/{draft_campaign.id}/send")
    assert response.status_code == 400
    assert "no eligible recipients" in response.json()["detail"]


def test_send_campaign_not_draft_returns_400(
    client_test_user: TestClient, sending_campaign, monkeypatch
):
    monkeypatch.setattr(
        "app.commands.campaign.send_campaign_command.build_sendly_client",
        lambda: object(),
    )

    response = client_test_user.post(f"/campaigns/{sending_campaign.id}/send")
    assert response.status_code == 400


def test_list_campaign_recipients(
    client_test_user: TestClient, draft_campaign, test_contact, db
):
    from app.repositories.campaign_repository import CampaignRepository

    CampaignRepository(db).mark_sending(
        draft_campaign.id, "batch-123", recipient_contact_ids=[test_contact.id]
    )

    response = client_test_user.get(f"/campaigns/{draft_campaign.id}/recipients")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["contact"]["id"] == str(test_contact.id)
    assert data["items"][0]["contact"]["email"] == test_contact.email


def test_list_campaign_recipients_draft_campaign_is_empty(
    client_test_user: TestClient, draft_campaign
):
    response = client_test_user.get(f"/campaigns/{draft_campaign.id}/recipients")
    assert response.status_code == 200

    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_list_campaign_recipients_not_found(client_test_user: TestClient):
    response = client_test_user.get(f"/campaigns/{uuid4()}/recipients")
    assert response.status_code == 404


def test_get_campaign_stats(
    client_test_user: TestClient, draft_campaign, test_contact, db
):
    from app.repositories.campaign_repository import CampaignRepository

    CampaignRepository(db).mark_sending(
        draft_campaign.id, "batch-123", recipient_contact_ids=[test_contact.id]
    )

    response = client_test_user.get(f"/campaigns/{draft_campaign.id}/stats")
    assert response.status_code == 200

    data = response.json()
    assert data["recipient_count"] == 1
    assert data["delivery_rate"] == 0.0
    assert "open_rate" in data
    assert "complaint_rate" in data


def test_get_campaign_stats_not_found(client_test_user: TestClient):
    response = client_test_user.get(f"/campaigns/{uuid4()}/stats")
    assert response.status_code == 404


def test_get_campaign_engagement_timeline(client_test_user: TestClient, draft_campaign):
    response = client_test_user.get(
        f"/campaigns/{draft_campaign.id}/stats/engagement-timeline"
    )
    assert response.status_code == 200

    data = response.json()
    assert len(data["buckets"]) == 7
    assert all(b["opened_count"] == 0 for b in data["buckets"])


def test_get_campaign_engagement_timeline_not_found(client_test_user: TestClient):
    response = client_test_user.get(f"/campaigns/{uuid4()}/stats/engagement-timeline")
    assert response.status_code == 404


def test_list_campaign_recipients_excludes_soft_deleted_contact(
    client_test_user: TestClient, draft_campaign, test_contact, db
):
    from datetime import datetime, timezone
    from app.repositories.campaign_repository import CampaignRepository

    CampaignRepository(db).mark_sending(
        draft_campaign.id, "batch-123", recipient_contact_ids=[test_contact.id]
    )
    test_contact.deleted_at = datetime.now(timezone.utc)
    db.commit()

    response = client_test_user.get(f"/campaigns/{draft_campaign.id}/recipients")
    assert response.status_code == 200

    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_duplicate_campaign(client_test_user: TestClient, draft_campaign, test_user):
    response = client_test_user.post(f"/campaigns/{draft_campaign.id}/duplicate")

    assert response.status_code == 201
    data = response.json()
    assert data["id"] != str(draft_campaign.id)
    assert data["name"] == f"Copy of {draft_campaign.name}"
    assert data["status"] == CampaignStatus.DRAFT.value
    assert data["html"] == draft_campaign.html
    assert data["layout_id"] == str(draft_campaign.layout_id)
    assert data["created_by_id"] == str(test_user.id)


def test_duplicate_sent_campaign_gives_a_clean_draft(
    client_test_user: TestClient, sending_campaign
):
    response = client_test_user.post(f"/campaigns/{sending_campaign.id}/duplicate")

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == CampaignStatus.DRAFT.value
    assert data["batch_id"] is None


def test_duplicate_campaign_not_found(client_test_user: TestClient):
    response = client_test_user.post(f"/campaigns/{uuid4()}/duplicate")
    assert response.status_code == 404


def _patch_test_send_sendly(monkeypatch, status="sent", error_message=None):
    class FakeSendlyClient:
        def render(self, request):
            return RenderResponse(html=request.html, subject=request.subject)

        def create_email(self, request):
            return CreateEmailResponse(
                from_email=str(request.from_email),
                to_email=str(request.to[0]),
                subject=request.subject,
                body=request.html,
                status=status,
                provider="fake",
                provider_message_id="msg-router-test",
                id="email-router-test",
                error_message=error_message,
            )

    monkeypatch.setattr(
        "app.commands.campaign.send_test_campaign_command.build_sendly_client",
        lambda: FakeSendlyClient(),
    )


def test_test_send_campaign_success(
    client_test_user: TestClient, draft_campaign, test_contact, monkeypatch
):
    _patch_test_send_sendly(monkeypatch)

    response = client_test_user.post(
        f"/campaigns/{draft_campaign.id}/test-send",
        json={"contact_id": str(test_contact.id)},
    )
    assert response.status_code == 200

    data = response.json()
    assert data == {
        "email_id": "email-router-test",
        "to_email": test_contact.email,
        "subject": f"[TEST] {draft_campaign.subject}",
        "status": "sent",
    }


def test_test_send_campaign_not_found(
    client_test_user: TestClient, test_contact, monkeypatch
):
    _patch_test_send_sendly(monkeypatch)

    response = client_test_user.post(
        f"/campaigns/{uuid4()}/test-send",
        json={"contact_id": str(test_contact.id)},
    )
    assert response.status_code == 404


def test_test_send_campaign_unknown_contact_returns_400(
    client_test_user: TestClient, draft_campaign, monkeypatch
):
    _patch_test_send_sendly(monkeypatch)

    response = client_test_user.post(
        f"/campaigns/{draft_campaign.id}/test-send",
        json={"contact_id": str(uuid4())},
    )
    assert response.status_code == 400
    assert "not found" in response.json()["detail"]


def test_test_send_campaign_not_draft_returns_400(
    client_test_user: TestClient, sending_campaign, test_contact, monkeypatch
):
    _patch_test_send_sendly(monkeypatch)

    response = client_test_user.post(
        f"/campaigns/{sending_campaign.id}/test-send",
        json={"contact_id": str(test_contact.id)},
    )
    assert response.status_code == 400


def test_test_send_campaign_sendly_failure_returns_502(
    client_test_user: TestClient, draft_campaign, test_contact, monkeypatch
):
    _patch_test_send_sendly(monkeypatch, status="failed", error_message="bounced")

    response = client_test_user.post(
        f"/campaigns/{draft_campaign.id}/test-send",
        json={"contact_id": str(test_contact.id)},
    )
    assert response.status_code == 502
    assert "bounced" in response.json()["detail"]


def test_test_send_campaign_requires_contact_id(
    client_test_user: TestClient, draft_campaign
):
    response = client_test_user.post(
        f"/campaigns/{draft_campaign.id}/test-send", json={}
    )
    assert response.status_code == 422


def test_test_send_campaign_requires_contact_read(
    client_test_user: TestClient, draft_campaign, test_contact, monkeypatch
):
    _patch_test_send_sendly(monkeypatch)

    def deny_contact_read():
        raise HTTPException(status_code=403, detail="forbidden")

    client_test_user.app.dependency_overrides[contact_rbac["read"]] = deny_contact_read

    response = client_test_user.post(
        f"/campaigns/{draft_campaign.id}/test-send",
        json={"contact_id": str(test_contact.id)},
    )
    assert response.status_code == 403

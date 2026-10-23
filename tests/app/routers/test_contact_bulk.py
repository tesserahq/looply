from uuid import uuid4

from app.models.contact import Contact
from app.repositories.tag_repository import TagRepository

BULK_UPDATE = "/contacts/bulk-update"
BULK_DELETE = "/contacts/bulk-delete"


class TestContactBulkUpdate:
    """Tests for POST /contacts/bulk-update."""

    def test_changes_only_touch_sent_fields(
        self, client, db, test_contact, setup_contact
    ):
        first_name_before = test_contact.first_name

        response = client.post(
            BULK_UPDATE,
            json={
                "contact_ids": [str(test_contact.id), str(setup_contact.id)],
                "changes": {"company": "Acme Corp", "status": "inactive"},
            },
        )

        assert response.status_code == 200
        assert response.json() == {
            "requested_count": 2,
            "updated_count": 2,
            "skipped": [],
        }
        db.expire_all()
        updated = db.query(Contact).filter(Contact.id == test_contact.id).one()
        assert updated.company == "Acme Corp"
        assert updated.status == "inactive"
        assert updated.first_name == first_name_before

    def test_unknown_ids_are_skipped(self, client, test_contact):
        missing_id = str(uuid4())

        response = client.post(
            BULK_UPDATE,
            json={
                "contact_ids": [str(test_contact.id), missing_id],
                "changes": {"city": "Lisbon"},
            },
        )

        assert response.status_code == 200
        assert response.json() == {
            "requested_count": 2,
            "updated_count": 1,
            "skipped": [{"contact_id": missing_id, "reason": "not_found"}],
        }

    def test_duplicate_ids_are_counted_once(self, client, test_contact):
        response = client.post(
            BULK_UPDATE,
            json={
                "contact_ids": [str(test_contact.id), str(test_contact.id)],
                "changes": {"city": "Lisbon"},
            },
        )

        assert response.status_code == 200
        assert response.json()["requested_count"] == 1
        assert response.json()["updated_count"] == 1

    def test_explicit_null_clears_nullable_field(self, client, db, test_contact):
        response = client.post(
            BULK_UPDATE,
            json={"contact_ids": [str(test_contact.id)], "changes": {"company": None}},
        )

        assert response.status_code == 200
        db.expire_all()
        assert (
            db.query(Contact).filter(Contact.id == test_contact.id).one().company
            is None
        )

    def test_null_on_required_field_is_422(self, client, test_contact):
        for field in ("status", "contact_type"):
            response = client.post(
                BULK_UPDATE,
                json={"contact_ids": [str(test_contact.id)], "changes": {field: None}},
            )
            assert response.status_code == 422, field

    def test_fields_outside_the_allowlist_are_422(self, client, test_contact):
        for field, value in (
            ("email", "new@example.com"),
            ("phone", "+15550100"),
            ("external_id", "ext-1"),
            ("tags", ["vip"]),
            ("source", "manual"),
        ):
            response = client.post(
                BULK_UPDATE,
                json={
                    "contact_ids": [str(test_contact.id)],
                    "changes": {field: value},
                },
            )
            assert response.status_code == 422, field

    def test_requires_changes_or_add_tags(self, client, test_contact):
        ids = [str(test_contact.id)]

        without_either = client.post(BULK_UPDATE, json={"contact_ids": ids})
        empty_changes = client.post(
            BULK_UPDATE, json={"contact_ids": ids, "changes": {}}
        )

        assert without_either.status_code == 422
        assert empty_changes.status_code == 422

    def test_add_tags_keeps_existing_tags(self, client, db, test_contact, test_user):
        TagRepository(db).set_contact_tags(test_contact.id, ["existing"], test_user.id)
        db.commit()

        response = client.post(
            BULK_UPDATE,
            json={"contact_ids": [str(test_contact.id)], "add_tags": ["vip"]},
        )

        assert response.status_code == 200
        assert response.json()["updated_count"] == 1
        names = {
            tag.name for tag in TagRepository(db).get_tags_for_contact(test_contact.id)
        }
        assert names == {"existing", "vip"}

    def test_add_tags_is_idempotent(self, client, db, test_contact):
        body = {"contact_ids": [str(test_contact.id)], "add_tags": ["vip", "VIP"]}

        first = client.post(BULK_UPDATE, json=body)
        second = client.post(BULK_UPDATE, json=body)

        assert first.status_code == 200
        assert second.status_code == 200
        names = [
            tag.name for tag in TagRepository(db).get_tags_for_contact(test_contact.id)
        ]
        assert names == ["vip"]

    def test_blank_tag_is_422(self, client, test_contact):
        response = client.post(
            BULK_UPDATE,
            json={"contact_ids": [str(test_contact.id)], "add_tags": ["  "]},
        )
        assert response.status_code == 422

    def test_too_many_tags_is_422(self, client, test_contact):
        response = client.post(
            BULK_UPDATE,
            json={
                "contact_ids": [str(test_contact.id)],
                "add_tags": [f"tag-{i}" for i in range(21)],
            },
        )
        assert response.status_code == 422

    def test_empty_contact_ids_is_422(self, client):
        response = client.post(
            BULK_UPDATE, json={"contact_ids": [], "changes": {"city": "Lisbon"}}
        )
        assert response.status_code == 422

    def test_too_many_contact_ids_is_422(self, client):
        response = client.post(
            BULK_UPDATE,
            json={
                "contact_ids": [str(uuid4()) for _ in range(501)],
                "changes": {"city": "Lisbon"},
            },
        )
        assert response.status_code == 422

    def test_invalid_status_is_422(self, client, test_contact):
        response = client.post(
            BULK_UPDATE,
            json={
                "contact_ids": [str(test_contact.id)],
                "changes": {"status": "archived"},
            },
        )
        assert response.status_code == 422


class TestContactBulkDelete:
    """Tests for POST /contacts/bulk-delete."""

    def test_soft_deletes_and_skips_unknown_ids(self, client, test_contact):
        missing_id = str(uuid4())

        response = client.post(
            BULK_DELETE,
            json={"contact_ids": [str(test_contact.id), missing_id]},
        )

        assert response.status_code == 200
        assert response.json() == {
            "requested_count": 2,
            "updated_count": 1,
            "skipped": [{"contact_id": missing_id, "reason": "not_found"}],
        }
        assert client.get(f"/contacts/{test_contact.id}").status_code == 404

    def test_already_deleted_contact_is_skipped(self, client, test_contact):
        client.delete(f"/contacts/{test_contact.id}")

        response = client.post(
            BULK_DELETE, json={"contact_ids": [str(test_contact.id)]}
        )

        assert response.status_code == 200
        assert response.json()["updated_count"] == 0
        assert response.json()["skipped"] == [
            {"contact_id": str(test_contact.id), "reason": "not_found"}
        ]

    def test_empty_contact_ids_is_422(self, client):
        response = client.post(BULK_DELETE, json={"contact_ids": []})
        assert response.status_code == 422

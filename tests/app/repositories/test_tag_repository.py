import pytest

from app.repositories.tag_repository import TagConflictError, TagRepository


def test_create_tag(db, test_user):
    tag = TagRepository(db).create_tag("VIP", test_user.id)

    assert tag.id is not None
    assert tag.name == "VIP"


def test_create_duplicate_tag_case_insensitive_conflict(db, test_user):
    repository = TagRepository(db)
    repository.create_tag("VIP", test_user.id)

    with pytest.raises(TagConflictError):
        repository.create_tag("vip", test_user.id)


def test_update_tag_rename(db, test_user):
    repository = TagRepository(db)
    tag = repository.create_tag("vip", test_user.id)

    renamed = repository.update_tag(tag.id, "VIP Customer")

    assert renamed.name == "VIP Customer"


def test_update_tag_rename_conflict(db, test_user):
    repository = TagRepository(db)
    repository.create_tag("vip", test_user.id)
    lead = repository.create_tag("lead", test_user.id)

    with pytest.raises(TagConflictError):
        repository.update_tag(lead.id, "VIP")


def test_delete_tag_removes_it_from_assigned_contacts(db, test_user, test_contact):
    tag_repository = TagRepository(db)
    tag_repository.set_contact_tags(test_contact.id, ["vip"], test_user.id)
    tag = tag_repository.get_by_name("vip")

    assert tag_repository.delete_tag(tag.id) is True
    assert tag_repository.get_tag(tag.id) is None
    assert tag_repository.get_tags_for_contact(test_contact.id) == []


def test_get_or_create_tags_reuses_existing_case_insensitively(db, test_user):
    repository = TagRepository(db)
    existing = repository.create_tag("vip", test_user.id)

    tags = repository.get_or_create_tags(["VIP", "new-tag"], test_user.id)

    assert {t.name for t in tags} == {"vip", "new-tag"}
    assert any(t.id == existing.id for t in tags)


def test_get_or_create_tags_dedupes_and_skips_blank(db, test_user):
    repository = TagRepository(db)
    tags = repository.get_or_create_tags(["vip", "VIP", "  ", "lead"], test_user.id)

    assert {t.name for t in tags} == {"vip", "lead"}


def test_set_contact_tags_replaces_full_set(db, test_user, test_contact):
    repository = TagRepository(db)
    repository.set_contact_tags(test_contact.id, ["vip", "lead"], test_user.id)

    repository.set_contact_tags(test_contact.id, ["lead"], test_user.id)

    names = {t.name for t in repository.get_tags_for_contact(test_contact.id)}
    assert names == {"lead"}


def test_get_contacts_by_tags_query_is_any_match(db, test_user, test_contact):
    repository = TagRepository(db)
    repository.set_contact_tags(test_contact.id, ["vip"], test_user.id)

    matches = repository.get_contacts_by_tags_query(["vip", "nonexistent"]).all()

    assert [c.id for c in matches] == [test_contact.id]


def test_get_tags_with_counts_query_reflects_assignments(db, test_user, test_contact):
    repository = TagRepository(db)
    repository.set_contact_tags(test_contact.id, ["vip"], test_user.id)
    repository.create_tag("unused", test_user.id)

    rows = {
        tag.name: (contacts, campaigns)
        for tag, contacts, campaigns in repository.get_tags_with_counts_query().all()
    }

    assert rows["vip"] == (1, 0)
    assert rows["unused"] == (0, 0)


def test_get_usage_counts_for_single_tag(db, test_user, test_contact):
    repository = TagRepository(db)
    repository.set_contact_tags(test_contact.id, ["vip"], test_user.id)
    tag = repository.get_by_name("vip")

    assert repository.get_usage_counts(tag.id) == (1, 0)

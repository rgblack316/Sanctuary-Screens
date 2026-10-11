"""Iteration 12 tests: Custom slide + Reference-only features.

Covers:
- /api/bible/publish with source_type custom/reference_only
- Validation: manual/local_lookup require verse_text (422)
- Prepared list with kind=custom and reference_only
- Switch translation on reference_only passage
- Cleanup: clear display + remove TEST prepared items
"""
import os
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
PIN = "1234"
SERVICE_DATE = "2099-01-04"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/api/auth/unlock", json={"pin": PIN, "area": "bible"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def default_code(h):
    r = requests.get(f"{BASE}/api/bible/translations", headers=h)
    assert r.status_code == 200
    code = r.json().get("default_translation")
    assert code, "No default translation installed"
    return code


@pytest.fixture(scope="module", autouse=True)
def cleanup(h):
    yield
    # Clear display to idle and remove any prepared items on SERVICE_DATE
    requests.post(f"{BASE}/api/bible/display/clear", headers=h)
    r = requests.get(f"{BASE}/api/bible/prepared", headers=h, params={"service_date": SERVICE_DATE})
    for it in r.json().get("items", []):
        requests.delete(f"{BASE}/api/bible/prepared/{it['id']}", headers=h)


class TestPublishCustom:
    def test_custom_two_slides_body_split(self, h):
        body = {
            "reference_input": "Hymn 245 – Amazing Grace",
            "normalized_reference": "Hymn 245 – Amazing Grace",
            "translation_code": None,
            "source_type": "custom",
            "verses": [
                {"reference_label": "Hymn 245 – Amazing Grace", "verse_text": "Page 312"},
                {"reference_label": "Hymn 245 – Amazing Grace", "verse_text": "Please stand"},
            ],
            "start_index": 0,
        }
        r = requests.post(f"{BASE}/api/bible/publish", headers=h, json=body)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["mode"] == "passage"
        assert d["total"] == 2
        assert d["source_type"] == "custom"
        # translation_code should be nulled for custom
        assert d.get("translation_code") in (None, "")

    def test_custom_title_only(self, h):
        body = {
            "reference_input": "Welcome",
            "normalized_reference": "Welcome",
            "translation_code": None,
            "source_type": "custom",
            "verses": [{"reference_label": "Welcome", "verse_text": ""}],
            "start_index": 0,
        }
        r = requests.post(f"{BASE}/api/bible/publish", headers=h, json=body)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["total"] == 1
        assert d["slide"]["verse_text"] == ""


class TestPublishReferenceOnly:
    def test_reference_only(self, h, default_code):
        body = {
            "reference_input": "John 3:16-18",
            "normalized_reference": "John 3:16-18",
            "translation_code": default_code,
            "source_type": "reference_only",
            "verses": [{"reference_label": "John 3:16-18", "verse_text": ""}],
            "start_index": 0,
        }
        r = requests.post(f"{BASE}/api/bible/publish", headers=h, json=body)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["total"] == 1
        assert d["source_type"] == "reference_only"
        assert d["translation_code"] == default_code
        assert d["slide"]["verse_text"] == ""


class TestValidation:
    def test_manual_requires_text(self, h):
        body = {
            "reference_input": "X",
            "normalized_reference": "X",
            "translation_code": None,
            "source_type": "manual",
            "verses": [{"reference_label": "X", "verse_text": ""}],
            "start_index": 0,
        }
        r = requests.post(f"{BASE}/api/bible/publish", headers=h, json=body)
        assert r.status_code == 422

    def test_local_lookup_requires_text(self, h, default_code):
        body = {
            "reference_input": "John 3:16",
            "normalized_reference": "John 3:16",
            "translation_code": default_code,
            "source_type": "local_lookup",
            "verses": [{"reference_label": "John 3:16", "verse_text": ""}],
            "start_index": 0,
        }
        r = requests.post(f"{BASE}/api/bible/publish", headers=h, json=body)
        assert r.status_code == 422


class TestSwitchTranslationReferenceOnly:
    def test_switch_keeps_reference_only(self, h, default_code):
        # Publish ref-only first
        body = {
            "reference_input": "John 3:16",
            "normalized_reference": "John 3:16",
            "translation_code": default_code,
            "source_type": "reference_only",
            "verses": [{"reference_label": "John 3:16", "verse_text": ""}],
            "start_index": 0,
        }
        r = requests.post(f"{BASE}/api/bible/publish", headers=h, json=body)
        assert r.status_code == 200
        # Switch to same code (only one translation likely); should still succeed
        r = requests.post(f"{BASE}/api/bible/display/translation", headers=h,
                          json={"translation_code": default_code})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["source_type"] == "reference_only"
        assert d["slide"]["verse_text"] == ""


class TestPreparedKindAndRefOnly:
    created_ids = []

    def test_create_custom_prepared(self, h):
        body = {
            "service_date": SERVICE_DATE,
            "title_or_note": "TEST_hymn",
            "reference": "Hymn 245 – Amazing Grace",
            "translation_code": None,
            "preloaded_text_optional": "Page 312\n---\nPlease stand",
            "kind": "custom",
            "reference_only": False,
        }
        r = requests.post(f"{BASE}/api/bible/prepared", headers=h, json=body)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["kind"] == "custom"
        assert d["reference"] == "Hymn 245 – Amazing Grace"
        self.__class__.created_ids.append(d["id"])

        # GET verifies persisted
        r = requests.get(f"{BASE}/api/bible/prepared", headers=h, params={"service_date": SERVICE_DATE})
        assert r.status_code == 200
        items = r.json()["items"]
        assert any(it["id"] == d["id"] and it["kind"] == "custom" for it in items)

    def test_create_reference_only_prepared(self, h, default_code):
        body = {
            "service_date": SERVICE_DATE,
            "title_or_note": "TEST_refonly",
            "reference": "John 3:16-18",
            "translation_code": default_code,
            "preloaded_text_optional": "",
            "kind": "scripture",
            "reference_only": True,
        }
        r = requests.post(f"{BASE}/api/bible/prepared", headers=h, json=body)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["reference_only"] is True
        assert d["kind"] == "scripture"
        self.__class__.created_ids.append(d["id"])

    def test_update_and_move_and_delete(self, h):
        # Fetch items for date (xdist safe)
        r = requests.get(f"{BASE}/api/bible/prepared", headers=h, params={"service_date": SERVICE_DATE})
        items = [it for it in r.json()["items"] if (it.get("title_or_note") or "").startswith("TEST_")]
        assert len(items) >= 2
        ids = [it["id"] for it in items]
        item_id = ids[0]
        # Edit
        r = requests.put(f"{BASE}/api/bible/prepared/{item_id}", headers=h, json={
            "service_date": SERVICE_DATE,
            "title_or_note": "TEST_hymn_edited",
            "reference": "Hymn 245 – Amazing Grace",
            "translation_code": None,
            "preloaded_text_optional": "Page 312",
            "kind": "custom",
            "reference_only": False,
        })
        assert r.status_code == 200
        assert r.json()["title_or_note"] == "TEST_hymn_edited"
        # Move down then up
        r = requests.post(f"{BASE}/api/bible/prepared/{item_id}/move", headers=h, json={"direction": "down"})
        assert r.status_code == 200
        r = requests.post(f"{BASE}/api/bible/prepared/{item_id}/move", headers=h, json={"direction": "up"})
        assert r.status_code == 200
        # Cleanup all created
        for iid in ids:
            r = requests.delete(f"{BASE}/api/bible/prepared/{iid}", headers=h)
            assert r.status_code == 200
        # Verify empty
        r = requests.get(f"{BASE}/api/bible/prepared", headers=h, params={"service_date": SERVICE_DATE})
        assert all(it["id"] not in ids for it in r.json()["items"])

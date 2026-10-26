"""Backend tests for bible slide library + hymnals (iteration 13)."""
import os
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
PIN = "1234"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/unlock", json={"pin": PIN, "area": "bible"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def auth(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module", autouse=True)
def cleanup(auth):
    yield
    # Teardown
    try:
        libs = auth.get(f"{BASE_URL}/api/bible/library").json().get("items", [])
        for it in libs:
            if it["name"].startswith("TEST"):
                auth.delete(f"{BASE_URL}/api/bible/library/{it['id']}")
        hs = auth.get(f"{BASE_URL}/api/bible/hymnals").json().get("hymnals", [])
        for h in hs:
            if h["name"].startswith("TEST"):
                auth.delete(f"{BASE_URL}/api/bible/hymnals/{h['id']}")
        auth.put(f"{BASE_URL}/api/bible/hymnals/last", json={"name": ""})
    except Exception as e:
        print("cleanup err", e)


class TestAuth:
    def test_library_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/bible/library")
        assert r.status_code == 401

    def test_hymnals_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/bible/hymnals")
        assert r.status_code == 401


class TestLibrary:
    created = []

    def test_create_custom_item(self, auth):
        body = {"name": "TEST Welcome", "kind": "custom", "reference": "TEST Welcome",
                "translation_code": None, "preloaded_text_optional": "Welcome!", "reference_only": False}
        r = auth.post(f"{BASE_URL}/api/bible/library", json=body)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["name"] == "TEST Welcome"
        assert d["kind"] == "custom"
        assert "id" in d
        TestLibrary.created.append(d["id"])

    def test_create_reference_only(self, auth):
        body = {"name": "TEST John 3:16 refonly", "kind": "scripture", "reference": "John 3:16",
                "translation_code": "KJV", "preloaded_text_optional": "", "reference_only": True}
        r = auth.post(f"{BASE_URL}/api/bible/library", json=body)
        assert r.status_code == 200
        TestLibrary.created.append(r.json()["id"])

    def test_create_scripture(self, auth):
        body = {"name": "TEST John 3:16", "kind": "scripture", "reference": "John 3:16",
                "translation_code": "KJV", "preloaded_text_optional": "", "reference_only": False}
        r = auth.post(f"{BASE_URL}/api/bible/library", json=body)
        assert r.status_code == 200
        TestLibrary.created.append(r.json()["id"])

    def test_duplicate_case_insensitive_409(self, auth):
        body = {"name": "test welcome", "kind": "custom", "reference": "Welcome",
                "preloaded_text_optional": "x", "reference_only": False}
        r = auth.post(f"{BASE_URL}/api/bible/library", json=body)
        assert r.status_code == 409

    def test_list_returns_items(self, auth):
        r = auth.get(f"{BASE_URL}/api/bible/library")
        assert r.status_code == 200
        items = r.json()["items"]
        names = [i["name"] for i in items]
        for n in ["TEST Welcome", "TEST John 3:16", "TEST John 3:16 refonly"]:
            assert n in names
        # Must not expose _id
        assert all("_id" not in i for i in items)

    def test_delete_item(self, auth):
        # Delete the first created
        _id = TestLibrary.created[0]
        r = auth.delete(f"{BASE_URL}/api/bible/library/{_id}")
        assert r.status_code == 200
        TestLibrary.created.remove(_id)
        # Verify gone
        items = auth.get(f"{BASE_URL}/api/bible/library").json()["items"]
        assert _id not in [i["id"] for i in items]

    def test_delete_nonexistent_404(self, auth):
        r = auth.delete(f"{BASE_URL}/api/bible/library/507f1f77bcf86cd799439011")
        assert r.status_code == 404

    def test_delete_bad_id_404(self, auth):
        r = auth.delete(f"{BASE_URL}/api/bible/library/not-an-oid")
        assert r.status_code == 404


class TestHymnals:
    created = []

    def test_create_hymnal(self, auth):
        r = auth.post(f"{BASE_URL}/api/bible/hymnals", json={"name": "TEST Blue Hymnal"})
        assert r.status_code == 200
        d = r.json()
        assert d["name"] == "TEST Blue Hymnal"
        TestHymnals.created.append(d["id"])

    def test_create_hymnal_dedupe_ci(self, auth):
        r = auth.post(f"{BASE_URL}/api/bible/hymnals", json={"name": "test blue hymnal"})
        assert r.status_code == 200
        d = r.json()
        assert d["id"] == TestHymnals.created[0]
        assert d["name"] == "TEST Blue Hymnal"

    def test_list_hymnals(self, auth):
        r = auth.get(f"{BASE_URL}/api/bible/hymnals")
        assert r.status_code == 200
        d = r.json()
        assert "hymnals" in d and "last_used" in d
        assert any(h["name"] == "TEST Blue Hymnal" for h in d["hymnals"])

    def test_set_last_used(self, auth):
        r = auth.put(f"{BASE_URL}/api/bible/hymnals/last", json={"name": "TEST Blue Hymnal"})
        assert r.status_code == 200
        assert r.json()["last_used"] == "TEST Blue Hymnal"
        # Verify
        d = auth.get(f"{BASE_URL}/api/bible/hymnals").json()
        assert d["last_used"] == "TEST Blue Hymnal"

    def test_delete_clears_last_if_match(self, auth):
        _id = TestHymnals.created[0]
        r = auth.delete(f"{BASE_URL}/api/bible/hymnals/{_id}")
        assert r.status_code == 200
        # Last used should be cleared
        d = auth.get(f"{BASE_URL}/api/bible/hymnals").json()
        assert d["last_used"] == ""
        TestHymnals.created.remove(_id)

    def test_delete_nonmatching_leaves_last(self, auth):
        # Create two, set last to #1, delete #2 -> last preserved
        a = auth.post(f"{BASE_URL}/api/bible/hymnals", json={"name": "TEST A"}).json()
        b = auth.post(f"{BASE_URL}/api/bible/hymnals", json={"name": "TEST B"}).json()
        auth.put(f"{BASE_URL}/api/bible/hymnals/last", json={"name": "TEST A"})
        r = auth.delete(f"{BASE_URL}/api/bible/hymnals/{b['id']}")
        assert r.status_code == 200
        d = auth.get(f"{BASE_URL}/api/bible/hymnals").json()
        assert d["last_used"] == "TEST A"
        # cleanup
        auth.delete(f"{BASE_URL}/api/bible/hymnals/{a['id']}")

    def test_delete_nonexistent_404(self, auth):
        r = auth.delete(f"{BASE_URL}/api/bible/hymnals/507f1f77bcf86cd799439099")
        assert r.status_code == 404

"""Tests for PUT /api/bible/library/{id} rename/edit + prepared propagation (iteration_14)."""
import os
import requests
import pytest

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
PIN = os.environ.get("ADMIN_PIN", "1234")
FAR_DATE = "2099-01-04"


@pytest.fixture(scope="module")
def auth():
    r = requests.post(f"{BASE}/api/auth/unlock", json={"pin": PIN, "area": "bible"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def cleanup(auth):
    created_lib, created_prep = [], []
    yield created_lib, created_prep
    for pid in created_prep:
        requests.delete(f"{BASE}/api/bible/prepared/{pid}", headers=auth)
    for lid in created_lib:
        requests.delete(f"{BASE}/api/bible/library/{lid}", headers=auth)


def _mk_lib(auth, name, **over):
    body = {"name": name, "kind": "scripture", "reference": "Psalm 1:1",
            "translation_code": "KJV", "preloaded_text_optional": "", "reference_only": False}
    body.update(over)
    r = requests.post(f"{BASE}/api/bible/library", json=body, headers=auth)
    assert r.status_code == 200, r.text
    return r.json()


class TestLibraryRename:
    def test_404_unknown_id(self, auth):
        r = requests.put(f"{BASE}/api/bible/library/507f1f77bcf86cd799439011",
                         json={"name": "TEST x", "kind": "scripture", "reference": "P 1:1"}, headers=auth)
        assert r.status_code == 404

    def test_404_bad_id(self, auth):
        r = requests.put(f"{BASE}/api/bible/library/garbage",
                         json={"name": "TEST x", "kind": "scripture", "reference": "P 1:1"}, headers=auth)
        assert r.status_code == 404

    def test_rename_same_name_allowed(self, auth, cleanup):
        libs, _ = cleanup
        a = _mk_lib(auth, "TEST Rename A")
        libs.append(a["id"])
        r = requests.put(f"{BASE}/api/bible/library/{a['id']}",
                         json={"name": "TEST Rename A", "kind": "scripture",
                               "reference": "Psalm 2:2", "translation_code": "KJV",
                               "preloaded_text_optional": "", "reference_only": False}, headers=auth)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["name"] == "TEST Rename A"
        assert d["reference"] == "Psalm 2:2"
        assert d["prepared_updated"] == 0

    def test_409_duplicate_case_insensitive(self, auth, cleanup):
        libs, _ = cleanup
        a = _mk_lib(auth, "TEST Dup A")
        b = _mk_lib(auth, "TEST Dup B")
        libs += [a["id"], b["id"]]
        r = requests.put(f"{BASE}/api/bible/library/{b['id']}",
                         json={"name": "test dup a", "kind": "scripture",
                               "reference": "Psalm 1:1", "translation_code": "KJV",
                               "preloaded_text_optional": "", "reference_only": False}, headers=auth)
        assert r.status_code == 409

    def test_update_propagates_to_linked_prepared_only(self, auth, cleanup):
        libs, preps = cleanup
        lib = _mk_lib(auth, "TEST Prop Orig", preloaded_text_optional="old text")
        libs.append(lib["id"])

        # linked prepared created from library with library_id
        r = requests.post(f"{BASE}/api/bible/prepared", json={
            "service_date": FAR_DATE, "title_or_note": lib["name"],
            "kind": "scripture", "reference": lib["reference"],
            "translation_code": "KJV", "preloaded_text_optional": "old text",
            "reference_only": False, "library_id": lib["id"],
        }, headers=auth)
        assert r.status_code == 200, r.text
        linked_id = r.json()["id"]
        preps.append(linked_id)

        # unlinked prepared with same date, no library_id
        r2 = requests.post(f"{BASE}/api/bible/prepared", json={
            "service_date": FAR_DATE, "title_or_note": "TEST untouched note",
            "kind": "scripture", "reference": "John 1:1",
            "translation_code": "KJV", "preloaded_text_optional": "orig",
            "reference_only": False,
        }, headers=auth)
        assert r2.status_code == 200, r2.text
        unlinked_id = r2.json()["id"]
        preps.append(unlinked_id)

        # rename + change content/kind/ref
        r3 = requests.put(f"{BASE}/api/bible/library/{lib['id']}", json={
            "name": "TEST Prop Renamed", "kind": "custom",
            "reference": "New Title", "translation_code": None,
            "preloaded_text_optional": "new body", "reference_only": True,
        }, headers=auth)
        assert r3.status_code == 200, r3.text
        assert r3.json()["prepared_updated"] == 1
        assert r3.json()["name"] == "TEST Prop Renamed"

        # verify linked prepared updated
        plist = requests.get(f"{BASE}/api/bible/prepared", params={"service_date": FAR_DATE}, headers=auth).json()
        items = {i["id"]: i for i in plist["items"]}
        linked = items[linked_id]
        assert linked["title_or_note"] == "TEST Prop Renamed"
        assert linked["kind"] == "custom"
        assert linked["reference"] == "New Title"
        assert linked["preloaded_text_optional"] == "new body"
        assert linked["reference_only"] is True
        assert linked["translation_code"] in (None, "")

        # verify unlinked untouched
        unl = items[unlinked_id]
        assert unl["title_or_note"] == "TEST untouched note"
        assert unl["reference"] == "John 1:1"
        assert unl["preloaded_text_optional"] == "orig"

    def test_list_is_alphabetical(self, auth, cleanup):
        libs, _ = cleanup
        for n in ["TEST zeta", "TEST alpha", "TEST mike"]:
            libs.append(_mk_lib(auth, n)["id"])
        data = requests.get(f"{BASE}/api/bible/library", headers=auth).json()
        names = [i["name"] for i in data["items"] if i["name"].startswith("TEST ")]
        assert names == sorted(names, key=str.lower)

    def test_auth_required(self):
        r = requests.put(f"{BASE}/api/bible/library/507f1f77bcf86cd799439011",
                         json={"name": "x", "kind": "scripture", "reference": "x"})
        assert r.status_code == 401

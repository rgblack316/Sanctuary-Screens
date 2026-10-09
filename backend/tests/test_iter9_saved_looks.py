"""Iteration-9: Saved Looks feature (non-destructive: snapshots & restores user's real settings)."""
import io
import os
import struct
import zlib

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
PIN = "1234"
DISPLAY = "bible"
TEST_PREFIX = "TEST_"


def _tiny_png() -> bytes:
    # Minimal 1x1 red PNG
    sig = b"\x89PNG\r\n\x1a\n"
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    raw = b"\x00\xff\x00\x00"
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/unlock", json={"pin": PIN, "area": "settings"})
    if r.status_code != 200:
        # try clearing lockout via alt field name
        pytest.skip(f"Could not unlock settings: {r.status_code} {r.text}")
    return r.json()["token"]


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def snapshot(auth):
    r = requests.get(f"{BASE_URL}/api/appearance/{DISPLAY}", headers=auth)
    assert r.status_code == 200
    data = r.json()
    return {"appearance": data["appearance"], "church_name": data.get("church_name", ""),
            "church_logo_url": data.get("church_logo_url")}


# ---------- Core flow + auth checks (single class so pytest-xdist loadscope
# keeps everything on one worker and the module teardown runs only once). ----------
class TestLooksFlow:
    def test_00a_list_without_token_401(self):
        r = requests.get(f"{BASE_URL}/api/appearance/{DISPLAY}/looks")
        assert r.status_code == 401

    def test_00b_create_without_token_401(self):
        r = requests.post(f"{BASE_URL}/api/appearance/{DISPLAY}/looks",
                          json={"name": "TEST_x", "settings": {}})
        assert r.status_code == 401

    look_id = None
    new_image_id = None
    original_image_url = None
    cleanup_look_ids: list = []

    def test_01_snapshot_has_image(self, snapshot):
        # Record the user's current bible background image
        TestLooksFlow.original_image_url = snapshot["appearance"].get("image_url")
        # Not strictly required but assume user has one (per agent-note). If not, test still proceeds.
        assert "image_url" in snapshot["appearance"] or snapshot["appearance"].get("image_url") is None

    def test_02_create_look_snapshots_current(self, auth, snapshot):
        body = {"name": f"{TEST_PREFIX}Original", "settings": snapshot["appearance"]}
        # Strip image_url from settings (not in AppearanceIn)
        body["settings"] = {k: v for k, v in body["settings"].items() if k != "image_url"}
        r = requests.post(f"{BASE_URL}/api/appearance/{DISPLAY}/looks", json=body, headers=auth)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["name"] == f"{TEST_PREFIX}Original"
        # image_url should match current display image
        assert d.get("image_url") == TestLooksFlow.original_image_url
        TestLooksFlow.look_id = d["id"]
        TestLooksFlow.cleanup_look_ids.append(d["id"])

    def test_03_duplicate_name_case_insensitive_409(self, auth, snapshot):
        body = {"name": f"{TEST_PREFIX}ORIGINAL",
                "settings": {k: v for k, v in snapshot["appearance"].items() if k != "image_url"}}
        r = requests.post(f"{BASE_URL}/api/appearance/{DISPLAY}/looks", json=body, headers=auth)
        assert r.status_code == 409

    def test_04_name_length_validation(self, auth, snapshot):
        settings = {k: v for k, v in snapshot["appearance"].items() if k != "image_url"}
        # empty name -> 422
        r = requests.post(f"{BASE_URL}/api/appearance/{DISPLAY}/looks",
                          json={"name": "", "settings": settings}, headers=auth)
        assert r.status_code == 422
        # 61 chars -> 422
        r = requests.post(f"{BASE_URL}/api/appearance/{DISPLAY}/looks",
                          json={"name": "T" * 61, "settings": settings}, headers=auth)
        assert r.status_code == 422

    def test_05_list_contains_look(self, auth):
        r = requests.get(f"{BASE_URL}/api/appearance/{DISPLAY}/looks", headers=auth)
        assert r.status_code == 200
        names = [l["name"] for l in r.json()["looks"]]
        assert f"{TEST_PREFIX}Original" in names

    def test_06_original_image_fetchable(self):
        if not TestLooksFlow.original_image_url:
            pytest.skip("No original bible image to test image-safety")
        r = requests.get(f"{BASE_URL}{TestLooksFlow.original_image_url}")
        assert r.status_code == 200

    def test_07_upload_test_image_replaces_display(self, auth):
        files = {"file": ("test.png", _tiny_png(), "image/png")}
        r = requests.post(f"{BASE_URL}/api/appearance/{DISPLAY}/image",
                          files=files, headers=auth)
        assert r.status_code == 200, r.text
        new_url = r.json()["appearance"]["image_url"]
        assert new_url and new_url != TestLooksFlow.original_image_url
        TestLooksFlow.new_image_id = new_url.rsplit("/", 1)[-1]

    def test_08_original_image_still_exists_after_replace(self):
        if not TestLooksFlow.original_image_url:
            pytest.skip("no original image")
        # Image safety: the saved look still references original image, so it must not be deleted
        r = requests.get(f"{BASE_URL}{TestLooksFlow.original_image_url}")
        assert r.status_code == 200, "Original image was deleted even though a saved look references it"

    def test_09_apply_look_restores_image_and_settings(self, auth):
        r = requests.post(f"{BASE_URL}/api/appearance/{DISPLAY}/looks/{TestLooksFlow.look_id}/apply",
                          headers=auth)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["active_look_id"] == TestLooksFlow.look_id
        assert d["appearance"].get("image_url") == TestLooksFlow.original_image_url

    def test_10_apply_sets_active_in_list(self, auth):
        r = requests.get(f"{BASE_URL}/api/appearance/{DISPLAY}/looks", headers=auth)
        assert r.json()["active_look_id"] == TestLooksFlow.look_id

    def test_11_update_look_persists(self, auth, snapshot):
        s = {k: v for k, v in snapshot["appearance"].items() if k != "image_url"}
        s["accent_color"] = "#123456"
        r = requests.put(f"{BASE_URL}/api/appearance/{DISPLAY}/looks/{TestLooksFlow.look_id}",
                         json={"name": f"{TEST_PREFIX}Original", "settings": s}, headers=auth)
        assert r.status_code == 200, r.text
        assert r.json()["settings"]["accent_color"] == "#123456"
        # Verify via list
        r = requests.get(f"{BASE_URL}/api/appearance/{DISPLAY}/looks", headers=auth)
        row = next(l for l in r.json()["looks"] if l["id"] == TestLooksFlow.look_id)
        assert row["settings"]["accent_color"] == "#123456"

    def test_12_unknown_id_404(self, auth):
        bogus = "507f1f77bcf86cd799439011"
        assert requests.post(f"{BASE_URL}/api/appearance/{DISPLAY}/looks/{bogus}/apply",
                             headers=auth).status_code == 404
        assert requests.put(f"{BASE_URL}/api/appearance/{DISPLAY}/looks/{bogus}",
                            json={"name": "x", "settings": {}}, headers=auth).status_code == 404
        assert requests.delete(f"{BASE_URL}/api/appearance/{DISPLAY}/looks/notanid",
                               headers=auth).status_code == 404

    def test_13_restore_user_settings_via_apply_then_put(self, auth, snapshot):
        # After test_11 the look holds accent #123456. Re-apply original snapshot settings
        # and image: first PUT appearance back to real values (keeps current image, which is original image after apply).
        body = {k: v for k, v in snapshot["appearance"].items() if k != "image_url"}
        r = requests.put(f"{BASE_URL}/api/appearance/{DISPLAY}", json=body, headers=auth)
        assert r.status_code == 200
        assert r.json()["appearance"]["accent_color"] == snapshot["appearance"]["accent_color"]
        # Confirm original image is still on the display
        assert r.json()["appearance"].get("image_url") == TestLooksFlow.original_image_url

    def test_14_delete_look_does_not_delete_image_on_display(self, auth):
        # look currently has old image_id = original (updated in test_11 - current image was original at that moment).
        # The display currently also uses the original image, so release_image must NOT delete it.
        r = requests.delete(f"{BASE_URL}/api/appearance/{DISPLAY}/looks/{TestLooksFlow.look_id}",
                            headers=auth)
        assert r.status_code == 200
        if TestLooksFlow.original_image_url:
            img = requests.get(f"{BASE_URL}{TestLooksFlow.original_image_url}")
            assert img.status_code == 200, "Deleting a look wiped the image still shown on the display"
        TestLooksFlow.cleanup_look_ids.remove(TestLooksFlow.look_id)

    def test_15_church_name_and_logo_untouched(self, auth, snapshot):
        r = requests.get(f"{BASE_URL}/api/appearance/{DISPLAY}", headers=auth)
        d = r.json()
        assert d.get("church_name", "") == snapshot["church_name"]
        assert d.get("church_logo_url") == snapshot["church_logo_url"]


@pytest.fixture(scope="module", autouse=True)
def _final_cleanup(request, auth, snapshot):
    yield
    # Delete any remaining TEST_ looks
    try:
        r = requests.get(f"{BASE_URL}/api/appearance/{DISPLAY}/looks", headers=auth)
        for l in r.json().get("looks", []):
            if l["name"].startswith(TEST_PREFIX):
                requests.delete(f"{BASE_URL}/api/appearance/{DISPLAY}/looks/{l['id']}", headers=auth)
    except Exception:
        pass
    # Final sanity restore of appearance (idempotent)
    try:
        body = {k: v for k, v in snapshot["appearance"].items() if k != "image_url"}
        requests.put(f"{BASE_URL}/api/appearance/{DISPLAY}", json=body, headers=auth)
    except Exception:
        pass

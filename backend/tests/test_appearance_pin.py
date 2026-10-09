"""Appearance + PIN change + token pin_version invalidation tests."""
import os
import io

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
PIN = "1234"


@pytest.fixture(scope="module")
def mongo():
    m = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    return m[os.environ.get("DB_NAME", "test_database")]


@pytest.fixture(autouse=True)
def _clear_lockout(mongo):
    mongo.pin_attempts.delete_many({})
    yield


@pytest.fixture
def s():
    return requests.Session()


def unlock(s, area, pin=PIN):
    r = s.post(f"{API}/auth/unlock", json={"pin": pin, "area": area})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture
def sh(s):
    return {"Authorization": f"Bearer {unlock(s, 'settings')}"}


@pytest.fixture
def rh(s):
    return {"Authorization": f"Bearer {unlock(s, 'register')}"}


@pytest.fixture
def bh(s):
    return {"Authorization": f"Bearer {unlock(s, 'bible')}"}


# ---------- settings auth ----------

class TestSettingsAuth:
    def test_settings_check(self, s, sh):
        r = s.get(f"{API}/auth/check/settings", headers=sh)
        assert r.status_code == 200

    def test_appearance_requires_settings_token(self, s, rh):
        r = s.get(f"{API}/appearance/register", headers=rh)
        assert r.status_code == 401

    def test_appearance_no_token_401(self, s):
        assert s.get(f"{API}/appearance/bible").status_code == 401


# ---------- appearance CRUD ----------

class TestAppearance:
    def test_get_defaults(self, s, sh):
        for d in ["register", "bible"]:
            r = s.get(f"{API}/appearance/{d}", headers=sh)
            assert r.status_code == 200
            data = r.json()
            assert "appearance" in data and "defaults" in data
            a = data["appearance"]
            for k in ["background_color", "text_color", "accent_color",
                      "muted_color", "panel_color", "panel_opacity",
                      "image_blur", "image_dim", "image_motion", "motion_speed"]:
                assert k in a
            assert a["image_url"] is None or isinstance(a["image_url"], str)

    def test_put_valid(self, s, sh):
        body = {
            "background_color": "#101020", "text_color": "#FAFAFA",
            "accent_color": "#22AAFF", "muted_color": "#889999",
            "panel_color": "#202030", "panel_opacity": 80,
            "image_blur": 5, "image_dim": 50,
            "image_motion": "parallax", "motion_speed": 6,
        }
        r = s.put(f"{API}/appearance/register", headers=sh, json=body)
        assert r.status_code == 200, r.text
        a = r.json()["appearance"]
        assert a["background_color"] == "#101020"
        assert a["image_motion"] == "parallax"
        assert a["panel_opacity"] == 80

    def test_invalid_hex_422(self, s, sh):
        body = {"background_color": "notahex"}
        r = s.put(f"{API}/appearance/bible", headers=sh, json=body)
        assert r.status_code == 422

    def test_invalid_opacity_422(self, s, sh):
        r = s.put(f"{API}/appearance/bible", headers=sh, json={"panel_opacity": 200})
        assert r.status_code == 422

    def test_appearance_in_public_register_display(self, s, sh):
        s.put(f"{API}/appearance/register", headers=sh, json={"accent_color": "#ABCDEF"})
        r = s.get(f"{API}/register/display")
        assert r.status_code == 200
        assert r.json().get("appearance", {}).get("accent_color") == "#ABCDEF"

    def test_appearance_in_public_bible_display(self, s, sh):
        s.put(f"{API}/appearance/bible", headers=sh, json={"text_color": "#112233"})
        r = s.get(f"{API}/bible/display")
        assert r.status_code == 200
        assert r.json().get("appearance", {}).get("text_color") == "#112233"


# ---------- image upload ----------

class TestImageUpload:
    def _jpeg(self):
        with open("/tmp/test_bg.jpg", "rb") as f:
            return f.read()

    def test_upload_jpeg_and_fetch_public(self, s, sh):
        data = self._jpeg()
        r = s.post(f"{API}/appearance/register/image", headers=sh,
                   files={"file": ("bg.jpg", data, "image/jpeg")})
        assert r.status_code == 200, r.text
        url = r.json()["appearance"]["image_url"]
        assert url and url.startswith("/api/appearance/image/")
        # public GET works without auth
        img = s.get(f"{BASE_URL}{url}")
        assert img.status_code == 200
        assert img.headers["content-type"] == "image/jpeg"
        assert len(img.content) == len(data)

    def test_upload_wrong_type_415(self, s, sh):
        r = s.post(f"{API}/appearance/bible/image", headers=sh,
                   files={"file": ("x.txt", b"hello", "text/plain")})
        assert r.status_code == 415

    def test_delete_image(self, s, sh):
        # ensure one exists
        s.post(f"{API}/appearance/register/image", headers=sh,
               files={"file": ("b.jpg", self._jpeg(), "image/jpeg")})
        r = s.delete(f"{API}/appearance/register/image", headers=sh)
        assert r.status_code == 200
        assert r.json()["appearance"]["image_url"] is None


# ---------- change pin ----------

class TestChangePin:
    def test_mismatch_new_pin_422(self, s, sh):
        # new_pin not 4 digits
        r = s.post(f"{API}/auth/change-pin", headers=sh,
                   json={"current_pin": "1234", "new_pin": "abcd"})
        assert r.status_code == 422

    def test_wrong_current_pin_401(self, s, sh, mongo):
        mongo.pin_attempts.delete_many({})
        r = s.post(f"{API}/auth/change-pin", headers=sh,
                   json={"current_pin": "0000", "new_pin": "5678"})
        assert r.status_code == 401
        assert "attempt" in r.json()["detail"].lower()
        mongo.pin_attempts.delete_many({})

    def test_full_change_flow_and_token_invalidation(self, s, sh, mongo):
        mongo.pin_attempts.delete_many({})
        # issue a register token first with current pin
        s2 = requests.Session()
        old_reg_token = unlock(s2, "register", "1234")
        # verify works
        assert s2.get(f"{API}/auth/check/register",
                      headers={"Authorization": f"Bearer {old_reg_token}"}).status_code == 200

        # change pin to 5678
        r = s.post(f"{API}/auth/change-pin", headers=sh,
                   json={"current_pin": "1234", "new_pin": "5678"})
        assert r.status_code == 200, r.text
        new_settings_token = r.json()["token"]

        # old register/bible token should be invalid (pv mismatch)
        r2 = s2.get(f"{API}/auth/check/register",
                    headers={"Authorization": f"Bearer {old_reg_token}"})
        assert r2.status_code == 401

        # unlock with old pin -> 401
        r3 = s2.post(f"{API}/auth/unlock", json={"pin": "1234", "area": "register"})
        assert r3.status_code == 401
        mongo.pin_attempts.delete_many({})

        # unlock with new pin -> 200
        r4 = s2.post(f"{API}/auth/unlock", json={"pin": "5678", "area": "register"})
        assert r4.status_code == 200

        # new settings token works
        r5 = s.get(f"{API}/auth/check/settings",
                   headers={"Authorization": f"Bearer {new_settings_token}"})
        assert r5.status_code == 200

        # restore pin to 1234
        rb = s.post(f"{API}/auth/change-pin",
                    headers={"Authorization": f"Bearer {new_settings_token}"},
                    json={"current_pin": "5678", "new_pin": "1234"})
        assert rb.status_code == 200
        mongo.pin_attempts.delete_many({})


# ---------- cleanup/teardown module ----------

def teardown_module(module):
    """Restore defaults, remove images, ensure PIN=1234."""
    try:
        m = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        db = m[os.environ.get("DB_NAME", "test_database")]
        db.pin_attempts.delete_many({})
    except Exception:
        pass
    try:
        s = requests.Session()
        tok = s.post(f"{API}/auth/unlock", json={"pin": "1234", "area": "settings"}).json().get("token")
        if not tok:
            # try 5678 just in case
            tok = s.post(f"{API}/auth/unlock", json={"pin": "5678", "area": "settings"}).json().get("token")
            if tok:
                s.post(f"{API}/auth/change-pin", headers={"Authorization": f"Bearer {tok}"},
                       json={"current_pin": "5678", "new_pin": "1234"})
                tok = s.post(f"{API}/auth/unlock", json={"pin": "1234", "area": "settings"}).json().get("token")
        if tok:
            h = {"Authorization": f"Bearer {tok}"}
            for d in ["register", "bible"]:
                s.delete(f"{API}/appearance/{d}/image", headers=h)
                s.put(f"{API}/appearance/{d}", headers=h, json={})
    except Exception as e:
        print("teardown err", e)

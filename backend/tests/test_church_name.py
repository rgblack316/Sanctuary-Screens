"""Church name feature tests (shared name + per-display styling)."""
import os

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
PIN = "1234"


@pytest.fixture(scope="module")
def mongo():
    m = MongoClient(os.environ["MONGO_URL"])
    return m[os.environ["DB_NAME"]]


@pytest.fixture(autouse=True)
def _clear(mongo):
    mongo.pin_attempts.delete_many({})
    yield


@pytest.fixture
def s():
    return requests.Session()


def _unlock(s, area):
    r = s.post(f"{API}/auth/unlock", json={"pin": PIN, "area": area})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture
def sh(s):
    return {"Authorization": f"Bearer {_unlock(s, 'settings')}"}


@pytest.fixture
def rh(s):
    return {"Authorization": f"Bearer {_unlock(s, 'register')}"}


# ---------- Church name endpoint auth + validation ----------

class TestChurchNameAuth:
    def test_no_token_401(self, s):
        r = s.put(f"{API}/appearance/church-name", json={"church_name": "x"})
        assert r.status_code == 401

    def test_wrong_area_token_401(self, s, rh):
        r = s.put(f"{API}/appearance/church-name", headers=rh, json={"church_name": "x"})
        assert r.status_code == 401

    def test_too_long_422(self, s, sh):
        r = s.put(f"{API}/appearance/church-name", headers=sh,
                  json={"church_name": "x" * 121})
        assert r.status_code == 422

    def test_set_trim_and_get(self, s, sh):
        r = s.put(f"{API}/appearance/church-name", headers=sh,
                  json={"church_name": "  Grace Chapel  "})
        assert r.status_code == 200
        assert r.json()["church_name"] == "Grace Chapel"
        # verify via settings GET
        g = s.get(f"{API}/appearance/register", headers=sh)
        assert g.status_code == 200
        assert g.json()["church_name"] == "Grace Chapel"

    def test_empty_allowed(self, s, sh):
        r = s.put(f"{API}/appearance/church-name", headers=sh, json={"church_name": ""})
        assert r.status_code == 200
        assert r.json()["church_name"] == ""


# ---------- Public display payloads include church_name ----------

class TestPublicIncludesChurchName:
    def test_register_display(self, s, sh):
        s.put(f"{API}/appearance/church-name", headers=sh, json={"church_name": "First Church"})
        r = s.get(f"{API}/register/display")
        assert r.status_code == 200
        assert r.json().get("church_name") == "First Church"

    def test_bible_display(self, s, sh):
        s.put(f"{API}/appearance/church-name", headers=sh, json={"church_name": "First Church"})
        r = s.get(f"{API}/bible/display")
        assert r.status_code == 200
        assert r.json().get("church_name") == "First Church"


# ---------- Appearance church_name_* fields ----------

class TestChurchNameAppearance:
    def test_defaults_include_fields(self, s, sh):
        for d in ["register", "bible"]:
            a = s.get(f"{API}/appearance/{d}", headers=sh).json()["appearance"]
            for k in ["church_name_show", "church_name_position", "church_name_size",
                      "church_name_color", "church_name_uppercase"]:
                assert k in a, f"missing {k} in {d}"
            assert a["church_name_position"] == "top-center"

    def test_valid_put(self, s, sh):
        body = {
            "church_name_show": True,
            "church_name_position": "bottom-right",
            "church_name_size": 7,
            "church_name_color": "#ABCDEF",
            "church_name_uppercase": False,
        }
        r = s.put(f"{API}/appearance/bible", headers=sh, json=body)
        assert r.status_code == 200, r.text
        a = r.json()["appearance"]
        assert a["church_name_position"] == "bottom-right"
        assert a["church_name_size"] == 7
        assert a["church_name_color"] == "#ABCDEF"
        assert a["church_name_uppercase"] is False
        assert a["church_name_show"] is True

    def test_invalid_position_422(self, s, sh):
        r = s.put(f"{API}/appearance/register", headers=sh,
                  json={"church_name_position": "middle-middle"})
        assert r.status_code == 422

    def test_invalid_color_422(self, s, sh):
        r = s.put(f"{API}/appearance/register", headers=sh,
                  json={"church_name_color": "notahex"})
        assert r.status_code == 422

    def test_invalid_size_422(self, s, sh):
        r = s.put(f"{API}/appearance/register", headers=sh,
                  json={"church_name_size": 99})
        assert r.status_code == 422

    def test_per_display_independence(self, s, sh):
        s.put(f"{API}/appearance/register", headers=sh,
              json={"church_name_position": "top-center", "church_name_show": True})
        s.put(f"{API}/appearance/bible", headers=sh,
              json={"church_name_position": "bottom-right", "church_name_show": False})
        reg = s.get(f"{API}/register/display").json()["appearance"]
        bib = s.get(f"{API}/bible/display").json()["appearance"]
        assert reg["church_name_position"] == "top-center"
        assert reg["church_name_show"] is True
        assert bib["church_name_position"] == "bottom-right"
        assert bib["church_name_show"] is False


# ---------- Regression: existing appearance still works ----------

class TestRegression:
    def test_appearance_core_fields(self, s, sh):
        body = {
            "background_color": "#101020", "accent_color": "#22AAFF",
            "panel_opacity": 55, "image_blur": 3, "image_dim": 40,
            "image_motion": "parallax", "motion_speed": 5,
        }
        r = s.put(f"{API}/appearance/register", headers=sh, json=body)
        assert r.status_code == 200
        a = r.json()["appearance"]
        assert a["background_color"] == "#101020"
        assert a["image_motion"] == "parallax"
        assert a["panel_opacity"] == 55


# ---------- Teardown: reset to defaults ----------

def teardown_module(module):
    try:
        s = requests.Session()
        tok = s.post(f"{API}/auth/unlock", json={"pin": PIN, "area": "settings"}).json().get("token")
        if not tok:
            return
        h = {"Authorization": f"Bearer {tok}"}
        # Reset church name
        s.put(f"{API}/appearance/church-name", headers=h, json={"church_name": ""})
        # Reset each display to ITS OWN defaults (fetch defaults then PUT them)
        for d in ["register", "bible"]:
            data = s.get(f"{API}/appearance/{d}", headers=h).json()
            defaults = data.get("defaults") or {}
            # strip non-model fields
            defaults.pop("image_url", None)
            s.put(f"{API}/appearance/{d}", headers=h, json=defaults)
            s.delete(f"{API}/appearance/{d}/image", headers=h)
        # Clear bible display
        s.post(f"{API}/bible/clear", headers=h)
        m = MongoClient(os.environ["MONGO_URL"])
        m[os.environ["DB_NAME"]].pin_attempts.delete_many({})
    except Exception as e:
        print("teardown err", e)

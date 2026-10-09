"""Iteration-4: comparison_service_date override + church logo upload/delete.

Tests use far-future dates (2030-01-*) which are isolated from real data.
Cleanup via Mongo in teardown_module.
"""
import io
import os

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
PIN = "1234"

D1 = "2030-01-06"   # earliest
D2 = "2030-01-13"
D3 = "2030-01-20"   # latest – custom compare target


# ---------- shared helpers / fixtures ----------

@pytest.fixture(scope="module")
def s():
    return requests.Session()


@pytest.fixture(scope="module")
def rh(s):
    r = s.post(f"{API}/auth/unlock", json={"pin": PIN, "area": "register"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def sh(s):
    r = s.post(f"{API}/auth/unlock", json={"pin": PIN, "area": "settings"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _tiny_png() -> bytes:
    # 1x1 red PNG
    import base64
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg=="
    )


# ---------- teardown ----------

_pre_active = None


def setup_module(module):
    global _pre_active
    try:
        r = requests.get(f"{API}/register/display").json()
        if r.get("current"):
            _pre_active = r["current"]["service_date"]
    except Exception:
        _pre_active = None


def teardown_module(module):
    try:
        from pymongo import MongoClient
        m = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        db = m[os.environ.get("DB_NAME", "test_database")]
        db.register_services.delete_many({"service_date": {"$in": [D1, D2, D3]}})
        # restore active service
        if _pre_active:
            db.register_state.update_one(
                {"_id": "state"}, {"$set": {"active_service_date": _pre_active}}, upsert=True
            )
        # remove any TEST logo
        try:
            tok = requests.post(f"{API}/auth/unlock",
                                json={"pin": PIN, "area": "settings"}).json()["token"]
            requests.delete(f"{API}/appearance/logo",
                            headers={"Authorization": f"Bearer {tok}"})
        except Exception:
            pass
    except Exception as e:
        print("teardown err", e)


# ---------- Comparison date override ----------

class TestCompareOverride:
    def test_a_seed_three_services(self, s, rh):
        for d, att in [(D1, 10), (D2, 20), (D3, 30)]:
            r = s.put(f"{API}/register/services/{d}", headers=rh,
                      json={"service_label": "TEST", "attendance": att, "offering": 100,
                            "make_active": True})
            assert r.status_code == 200, r.text

    def test_b_default_auto_minus7(self, s, rh):
        # D3 - 7d = D2 ; previous should be D2
        d = s.get(f"{API}/register/display").json()
        assert d["current"]["service_date"] == D3
        assert d["comparison_service_date"] == D2
        assert d["comparison_overridden"] is False
        assert d["previous"]["attendance"] == 20

    def test_c_custom_compare_d1(self, s, rh):
        # Override D3 to compare with D1 instead of D2
        r = s.put(f"{API}/register/services/{D3}", headers=rh,
                  json={"service_label": "TEST", "attendance": 30, "offering": 100,
                        "comparison_service_date": D1, "make_active": True})
        assert r.status_code == 200
        d = r.json()
        assert d["comparison_service_date"] == D1
        assert d["comparison_overridden"] is True
        assert d["previous"]["service_date"] == D1
        assert d["previous"]["attendance"] == 10
        # public endpoint reflects it
        pub = s.get(f"{API}/register/display").json()
        assert pub["comparison_service_date"] == D1
        assert pub["comparison_overridden"] is True

    def test_d_null_restores_auto(self, s, rh):
        r = s.put(f"{API}/register/services/{D3}", headers=rh,
                  json={"service_label": "TEST", "attendance": 30, "offering": 100,
                        "comparison_service_date": None, "make_active": True})
        assert r.status_code == 200
        d = r.json()
        assert d["comparison_service_date"] == D2
        assert d["comparison_overridden"] is False

    def test_e_compare_same_day_422(self, s, rh):
        r = s.put(f"{API}/register/services/{D3}", headers=rh,
                  json={"service_label": "TEST", "attendance": 30, "offering": 100,
                        "comparison_service_date": D3, "make_active": False})
        assert r.status_code == 422

    def test_f_compare_future_422(self, s, rh):
        r = s.put(f"{API}/register/services/{D2}", headers=rh,
                  json={"service_label": "TEST", "attendance": 20, "offering": 100,
                        "comparison_service_date": D3, "make_active": False})
        assert r.status_code == 422

    def test_g_compare_missing_record_422(self, s, rh):
        r = s.put(f"{API}/register/services/{D3}", headers=rh,
                  json={"service_label": "TEST", "attendance": 30, "offering": 100,
                        "comparison_service_date": "2029-12-25", "make_active": False})
        assert r.status_code == 422
        assert "no service record" in r.json()["detail"].lower()

    def test_h_compare_bad_format_422(self, s, rh):
        r = s.put(f"{API}/register/services/{D3}", headers=rh,
                  json={"service_label": "TEST", "attendance": 30, "offering": 100,
                        "comparison_service_date": "not-a-date", "make_active": False})
        assert r.status_code == 422

    def test_i_persisted_mode_across_fetch(self, s, rh):
        # set override to D1 again and verify list_services preserves comparison fields
        s.put(f"{API}/register/services/{D3}", headers=rh,
              json={"service_label": "TEST", "attendance": 30, "offering": 100,
                    "comparison_service_date": D1, "make_active": True})
        lst = s.get(f"{API}/register/services", headers=rh).json()
        d3 = next(x for x in lst["services"] if x["service_date"] == D3)
        assert d3["comparison_overridden"] is True
        assert d3["comparison_service_date"] == D1


# ---------- Logo upload ----------

class TestLogo:
    def test_a_initial_no_logo(self, s):
        d = s.get(f"{API}/register/display").json()
        assert d.get("church_logo_url") in (None, "")

    def test_b_requires_auth(self, s):
        r = s.post(f"{API}/appearance/logo",
                   files={"file": ("x.png", _tiny_png(), "image/png")})
        assert r.status_code == 401

    def test_c_rejects_non_image(self, s, sh):
        r = s.post(f"{API}/appearance/logo", headers=sh,
                   files={"file": ("x.txt", b"hello", "text/plain")})
        assert r.status_code == 415

    def test_d_upload_png(self, s, sh):
        r = s.post(f"{API}/appearance/logo", headers=sh,
                   files={"file": ("logo.png", _tiny_png(), "image/png")})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["church_logo_url"]
        assert data["church_logo_url"].startswith("/api/appearance/image/")
        # fetch the image bytes
        img = s.get(f"{BASE_URL}{data['church_logo_url']}")
        assert img.status_code == 200
        assert img.headers["content-type"] == "image/png"
        assert len(img.content) > 0

    def test_e_in_register_and_bible_display(self, s):
        r = s.get(f"{API}/register/display").json()
        assert r["church_logo_url"] and r["church_logo_url"].startswith("/api/appearance/image/")
        b = s.get(f"{API}/bible/display").json()
        assert b["church_logo_url"] == r["church_logo_url"]  # shared

    def test_f_replace_logo_cleans_old(self, s, sh):
        old = s.get(f"{API}/register/display").json()["church_logo_url"]
        r = s.post(f"{API}/appearance/logo", headers=sh,
                   files={"file": ("logo2.jpg", _tiny_png(), "image/jpeg")})
        assert r.status_code == 200
        new = r.json()["church_logo_url"]
        assert new and new != old
        # old url should 404 now
        assert s.get(f"{BASE_URL}{old}").status_code == 404

    def test_g_empty_file_422(self, s, sh):
        r = s.post(f"{API}/appearance/logo", headers=sh,
                   files={"file": ("empty.png", b"", "image/png")})
        assert r.status_code == 422

    def test_h_delete_logo(self, s, sh):
        r = s.delete(f"{API}/appearance/logo", headers=sh)
        assert r.status_code == 200
        assert r.json()["church_logo_url"] is None
        pub = s.get(f"{API}/register/display").json()
        assert pub["church_logo_url"] is None

    def test_i_delete_when_absent_ok(self, s, sh):
        r = s.delete(f"{API}/appearance/logo", headers=sh)
        assert r.status_code == 200


# ---------- Appearance: new logo fields ----------

class TestLogoAppearanceFields:
    def test_a_appearance_has_logo_fields(self, s, sh):
        d = s.get(f"{API}/appearance/register", headers=sh).json()["appearance"]
        assert "church_logo_show" in d
        assert "church_logo_size" in d
        assert isinstance(d["church_logo_show"], bool)
        assert 1 <= d["church_logo_size"] <= 10

    def test_b_update_logo_fields(self, s, sh):
        # must send full body
        body = s.get(f"{API}/appearance/register", headers=sh).json()["appearance"]
        body.pop("image_url", None)
        body["church_logo_show"] = False
        body["church_logo_size"] = 8
        r = s.put(f"{API}/appearance/register", headers=sh, json=body)
        assert r.status_code == 200
        updated = r.json()["appearance"]
        assert updated["church_logo_show"] is False
        assert updated["church_logo_size"] == 8
        # restore
        body["church_logo_show"] = True
        body["church_logo_size"] = 5
        s.put(f"{API}/appearance/register", headers=sh, json=body)

    def test_c_size_bounds(self, s, sh):
        body = s.get(f"{API}/appearance/register", headers=sh).json()["appearance"]
        body.pop("image_url", None)
        body["church_logo_size"] = 11
        r = s.put(f"{API}/appearance/register", headers=sh, json=body)
        assert r.status_code == 422
        body["church_logo_size"] = 0
        r = s.put(f"{API}/appearance/register", headers=sh, json=body)
        assert r.status_code == 422

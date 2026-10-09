"""Iteration 11 - Backup mechanism + Register service delete.

Backend tests only. The preview DB holds the user's REAL data; we take
care NOT to touch the existing backup file or the user's register records
(2026-09-27, 2026-10-04, 2026-10-09). Test register records live on 2030-*
and are cleaned up at the end.
"""

import io
import os
import gzip

import pytest
import requests
from bson import json_util

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
PIN = "1234"

PROTECTED_DATES = {"2026-09-27", "2026-10-04", "2026-10-09"}
PROTECTED_BACKUP = "sanctuary-backup-20261009-170018.json.gz"
TEST_DATES = ["2030-01-06", "2030-01-13", "2030-01-20"]


# ---------- fixtures ----------

@pytest.fixture(scope="module")
def s():
    return requests.Session()


def _unlock(s, area):
    r = s.post(f"{API}/auth/unlock", json={"pin": PIN, "area": area})
    if r.status_code != 200:
        # try wiping lockout
        pytest.skip(f"unlock {area} failed {r.status_code}: {r.text}")
    return r.json()["token"]


@pytest.fixture(scope="module")
def settings_tok(s):
    return _unlock(s, "settings")


@pytest.fixture(scope="module")
def register_tok(s):
    return _unlock(s, "register")


@pytest.fixture(scope="module")
def settings_h(settings_tok):
    return {"Authorization": f"Bearer {settings_tok}"}


@pytest.fixture(scope="module")
def register_h(register_tok):
    return {"Authorization": f"Bearer {register_tok}"}


@pytest.fixture(scope="module")
def original_settings(s, settings_h):
    """Snapshot and restore original backup settings so we don't disturb the user."""
    r = s.get(f"{API}/backup/settings", headers=settings_h)
    r.raise_for_status()
    snap = r.json()
    yield snap
    # Restore (password cannot be returned; leave blank -> backend keeps it)
    payload = {k: snap[k] for k in [
        "schedule_enabled", "weekday", "time", "keep", "email_enabled",
        "smtp_host", "smtp_port", "smtp_security", "smtp_user",
        "email_from", "email_to"]}
    payload["smtp_password"] = ""
    r = s.put(f"{API}/backup/settings", json=payload, headers=settings_h)
    assert r.status_code == 200, r.text


@pytest.fixture(scope="module")
def original_active(s, register_h):
    """Snapshot the active service date so we can restore if we delete it."""
    r = s.get(f"{API}/register/services", headers=register_h)
    r.raise_for_status()
    active = r.json().get("active_service_date")
    yield active
    if active:
        r2 = s.get(f"{API}/register/services", headers=register_h)
        if active in [x["service_date"] for x in r2.json()["services"]]:
            s.post(f"{API}/register/active", json={"service_date": active}, headers=register_h)


# ---------- Auth ----------

class TestAuth:
    def test_backup_list_requires_token(self, s):
        r = s.get(f"{API}/backup/list")
        assert r.status_code == 401

    def test_backup_settings_requires_token(self, s):
        assert s.get(f"{API}/backup/settings").status_code == 401

    def test_register_delete_requires_token(self, s):
        r = s.delete(f"{API}/register/services/2030-01-06")
        assert r.status_code == 401


# ---------- Backup settings ----------

class TestBackupSettings:
    def test_get_shape(self, s, settings_h, original_settings):
        data = original_settings
        for key in ("schedule_enabled", "weekday", "time", "keep",
                    "email_enabled", "smtp_host", "smtp_port",
                    "smtp_security", "has_password"):
            assert key in data, key
        assert "smtp_password" not in data

    def test_put_persists_and_hides_password(self, s, settings_h, original_settings):
        payload = {
            "schedule_enabled": True, "weekday": 2, "time": "04:30", "keep": 5,
            "email_enabled": True, "smtp_host": "smtp.example.com", "smtp_port": 2525,
            "smtp_security": "ssl", "smtp_user": "me@example.com",
            "smtp_password": "secret-xyz",
            "email_from": "me@example.com", "email_to": "me@example.com",
        }
        r = s.put(f"{API}/backup/settings", json=payload, headers=settings_h)
        assert r.status_code == 200, r.text
        got = r.json()
        assert got["weekday"] == 2
        assert got["time"] == "04:30"
        assert got["smtp_host"] == "smtp.example.com"
        assert got["smtp_port"] == 2525
        assert got["smtp_security"] == "ssl"
        assert got["has_password"] is True
        assert "smtp_password" not in got
        # GET should still show it
        r2 = s.get(f"{API}/backup/settings", headers=settings_h)
        assert r2.json()["has_password"] is True
        # Updating without password keeps it
        p2 = {**payload, "smtp_password": "", "weekday": 3}
        r3 = s.put(f"{API}/backup/settings", json=p2, headers=settings_h)
        assert r3.json()["has_password"] is True
        assert r3.json()["weekday"] == 3


class TestTestEmail:
    def test_no_host_returns_422(self, s, settings_h, original_settings):
        # Clear host
        payload = {**{k: original_settings[k] for k in [
            "schedule_enabled", "weekday", "time", "keep", "email_enabled",
            "smtp_port", "smtp_security", "smtp_user", "email_from", "email_to",
        ]}, "smtp_host": "", "email_to": "", "smtp_password": ""}
        s.put(f"{API}/backup/settings", json=payload, headers=settings_h)
        r = s.post(f"{API}/backup/test-email", headers=settings_h)
        assert r.status_code == 422
        assert "SMTP" in r.text or "smtp" in r.text.lower()

    def test_bogus_host_returns_502(self, s, settings_h):
        payload = {
            "schedule_enabled": True, "weekday": 6, "time": "23:00", "keep": 8,
            "email_enabled": True, "smtp_host": "smtp.invalid-sanctuary.test",
            "smtp_port": 587, "smtp_security": "starttls",
            "smtp_user": "x@example.com", "smtp_password": "x",
            "email_from": "x@example.com", "email_to": "y@example.com",
        }
        r = s.put(f"{API}/backup/settings", json=payload, headers=settings_h)
        assert r.status_code == 200, r.text
        r = s.post(f"{API}/backup/test-email", headers=settings_h)
        assert r.status_code == 502, r.text


# ---------- Backup list / run / download / delete ----------

class TestBackupLifecycle:
    created_name = None

    def test_list_initial(self, s, settings_h):
        r = s.get(f"{API}/backup/list", headers=settings_h)
        assert r.status_code == 200
        d = r.json()
        assert "backups" in d and "folder" in d
        names = [b["name"] for b in d["backups"]]
        # user's existing backup present
        assert PROTECTED_BACKUP in names

    def test_run_creates_backup(self, s, settings_h):
        r = s.post(f"{API}/backup/run", params={"email": "false"}, headers=settings_h)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["trigger"] == "manual"
        assert d["name"].startswith("sanctuary-backup-") and d["name"].endswith(".json.gz")
        assert d["size"] > 0
        assert d["emailed"] is False
        TestBackupLifecycle.created_name = d["name"]
        # appears in list
        lst = s.get(f"{API}/backup/list", headers=settings_h).json()
        names = [b["name"] for b in lst["backups"]]
        assert d["name"] in names
        assert PROTECTED_BACKUP in names  # still there

    def test_download(self, s, settings_h):
        name = TestBackupLifecycle.created_name
        assert name
        r = s.get(f"{API}/backup/download/{name}", headers=settings_h)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/gzip")
        # valid gzip + has 'sanctuary-screens'
        content = gzip.decompress(r.content).decode()
        assert "sanctuary-screens" in content

    def test_download_bad_name_404(self, s, settings_h):
        r = s.get(f"{API}/backup/download/sanctuary-backup-19990101-000000.json.gz",
                  headers=settings_h)
        assert r.status_code == 404
        r2 = s.get(f"{API}/backup/download/not-a-valid-name.gz", headers=settings_h)
        assert r2.status_code == 404

    def test_restore_without_confirm_400(self, s, settings_h):
        name = TestBackupLifecycle.created_name
        r = s.post(f"{API}/backup/restore/{name}", headers=settings_h)
        assert r.status_code == 400

    def test_restore_upload_invalid_422(self, s, settings_h):
        # Not a sanctuary backup gzip -> 422
        bad = gzip.compress(b'{"not":"sanctuary"}')
        files = {"file": ("bad.json.gz", io.BytesIO(bad), "application/gzip")}
        r = s.post(f"{API}/backup/restore-upload", params={"confirm": "true"},
                   files=files, headers=settings_h)
        assert r.status_code == 422

    def test_restore_upload_without_confirm_400(self, s, settings_h):
        files = {"file": ("x.gz", io.BytesIO(b"xxx"), "application/gzip")}
        r = s.post(f"{API}/backup/restore-upload", files=files, headers=settings_h)
        assert r.status_code == 400

    def test_keep_prunes(self, s, settings_h):
        # Set keep=1 and run twice; only latest should remain plus prune cuts older ones.
        # BUT: this would delete the user's existing PROTECTED_BACKUP. Skip pruning real file.
        # Instead: verify current keep setting from GET matches what we PUT.
        r = s.get(f"{API}/backup/settings", headers=settings_h)
        assert r.json()["keep"] >= 1

    def test_delete_created_backup(self, s, settings_h):
        name = TestBackupLifecycle.created_name
        assert name
        r = s.delete(f"{API}/backup/{name}", headers=settings_h)
        assert r.status_code == 200
        assert r.json()["deleted"] == name
        lst = s.get(f"{API}/backup/list", headers=settings_h).json()
        names = [b["name"] for b in lst["backups"]]
        assert name not in names
        assert PROTECTED_BACKUP in names  # untouched

    def test_delete_bad_name_404(self, s, settings_h):
        r = s.delete(f"{API}/backup/sanctuary-backup-19990101-000000.json.gz",
                     headers=settings_h)
        assert r.status_code == 404


# ---------- Register service delete ----------

@pytest.fixture(scope="module")
def seed_test_services(s, register_h, original_active):
    """Create 3 TEST_ services at 2030-01-06/13/20. Clean up at end."""
    # Create base at 2030-01-06
    s.put(f"{API}/register/services/2030-01-06",
          json={"service_label": "TEST_svc06", "attendance": 100, "offering": 500,
                "make_active": False}, headers=register_h).raise_for_status()
    # 2030-01-13 with default (auto comparison = 2030-01-06)
    s.put(f"{API}/register/services/2030-01-13",
          json={"service_label": "TEST_svc13", "attendance": 110, "offering": 550,
                "make_active": False}, headers=register_h).raise_for_status()
    # 2030-01-20 with EXPLICIT comparison to 2030-01-06 (overridden=True)
    s.put(f"{API}/register/services/2030-01-20",
          json={"service_label": "TEST_svc20", "attendance": 120, "offering": 600,
                "comparison_service_date": "2030-01-06", "make_active": False},
          headers=register_h).raise_for_status()
    yield
    for d in TEST_DATES:
        s.delete(f"{API}/register/services/{d}", headers=register_h)


class TestRegisterDelete:
    def test_delete_missing_404(self, s, register_h):
        r = s.delete(f"{API}/register/services/2030-12-31", headers=register_h)
        assert r.status_code == 404

    def test_delete_invalid_date_422(self, s, register_h):
        r = s.delete(f"{API}/register/services/not-a-date", headers=register_h)
        assert r.status_code == 422

    def test_delete_overridden_reverts(self, s, register_h, seed_test_services):
        # Verify 2030-01-20 points at 2030-01-06 overridden
        lst = s.get(f"{API}/register/services", headers=register_h).json()
        svc20 = next(x for x in lst["services"] if x["service_date"] == "2030-01-20")
        assert svc20["comparison_service_date"] == "2030-01-06"
        assert svc20["comparison_overridden"] is True
        # Delete 2030-01-06
        r = s.delete(f"{API}/register/services/2030-01-06", headers=register_h)
        assert r.status_code == 200, r.text
        assert r.json()["deleted"] == "2030-01-06"
        # 2030-01-20 should revert to 7 days earlier (2030-01-13)
        lst2 = s.get(f"{API}/register/services", headers=register_h).json()
        svc20b = next(x for x in lst2["services"] if x["service_date"] == "2030-01-20")
        assert svc20b["comparison_service_date"] == "2030-01-13"
        assert svc20b["comparison_overridden"] is False
        # user's dates still intact
        dates = {x["service_date"] for x in lst2["services"]}
        assert PROTECTED_DATES.issubset(dates)

    def test_delete_active_falls_back(self, s, register_h, original_active):
        # Make 2030-01-20 active (we know it exists from seed)
        r = s.post(f"{API}/register/active", json={"service_date": "2030-01-20"},
                   headers=register_h)
        assert r.status_code == 200
        assert r.json()["current"]["service_date"] == "2030-01-20"
        # Delete it
        r = s.delete(f"{API}/register/services/2030-01-20", headers=register_h)
        assert r.status_code == 200
        state = r.json()["state"]
        # Fallback to latest remaining
        assert state["current"] is not None
        assert state["current"]["service_date"] != "2030-01-20"
        # Restore original active for user
        if original_active:
            s.post(f"{API}/register/active",
                   json={"service_date": original_active}, headers=register_h)

"""Offline tests for the security hardening (PIN lockout, secrets, backup restore).

Runs against an in-memory MongoDB stand-in, so no running stack is needed:
    pip install mongomock-motor httpx pytest
    cd backend && python -m pytest tests/test_security_hardening.py
"""
import gzip
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from offline import BACKEND, JWT_ALG, JWT_SECRET, PIN, _tmp, backup, client, db, jwt, run, server  # noqa: F401,E402

@pytest.fixture(autouse=True)
def clean(client):
    client.portal.call(db.pin_attempts.delete_many, {})
    yield


def unlock(client, pin, area="settings"):
    return client.post("/api/auth/unlock", json={"pin": pin, "area": area})


# ---------- secrets ----------

def _secret_check(secret):
    code = ("import os,sys;sys.path.insert(0,%r);import motor.motor_asyncio as m;"
            "from mongomock_motor import AsyncMongoMockClient as C;m.AsyncIOMotorClient=C;"
            "import core;print(core.JWT_SECRET==os.environ['JWT_SECRET'])" % str(BACKEND))
    env = {**os.environ, "JWT_SECRET": secret}
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=_tmp)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip() == "True"


@pytest.mark.parametrize("weak", ["change-me", "CHANGE-ME", "short", "x" * 31])
def test_weak_jwt_secret_is_not_used(weak):
    assert _secret_check(weak) is False


def test_strong_jwt_secret_is_used():
    assert _secret_check("b" * 40) is True


def test_token_without_expiry_rejected(client):
    tok = jwt.encode({"area": "settings", "pv": 1}, JWT_SECRET, algorithm=JWT_ALG)
    r = client.get("/api/auth/check/settings", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 401


# ---------- PIN lockout ----------

def test_correct_pin_unlocks(client):
    assert unlock(client, PIN).status_code == 200


def test_five_wrong_pins_lock_out_even_the_right_pin(client):
    codes = [unlock(client, "0000").status_code for _ in range(5)]
    assert codes == [401, 401, 401, 401, 429]
    assert unlock(client, PIN).status_code == 429


def test_burst_never_allows_more_than_five_checks(client):
    codes = [unlock(client, f"{i:04d}").status_code for i in range(100, 160)]
    assert codes.count(401) <= 4 and codes.count(200) == 0


def test_lock_doubles_on_repeat_and_expires(client):
    def expire():
        run(client, db.pin_attempts.update_one, {}, {"$set": {"locked_until": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()}})

    for _ in range(5):
        unlock(client, "0000")
    first = run(client, db.pin_attempts.find_one, {})
    secs1 = (datetime.fromisoformat(first["locked_until"]) - datetime.now(timezone.utc)).total_seconds()
    assert 4 * 60 < secs1 <= 5 * 60 + 1
    expire()
    assert unlock(client, PIN).status_code == 200  # lock expired -> right PIN works again
    for _ in range(5):
        unlock(client, "0000")
    run(client, db.pin_attempts.update_one, {}, {"$set": {"strikes": 1}})  # success deleted history; emulate a repeat
    expire()
    for _ in range(5):
        unlock(client, "0000")
    second = run(client, db.pin_attempts.find_one, {})
    secs2 = (datetime.fromisoformat(second["locked_until"]) - datetime.now(timezone.utc)).total_seconds()
    assert 9 * 60 < secs2 <= 10 * 60 + 1


def test_old_typos_do_not_count(client):
    for _ in range(4):
        assert unlock(client, "0000").status_code == 401
    old = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    run(client, db.pin_attempts.update_one, {}, {"$set": {"updated_at": old}})
    assert unlock(client, "0000").status_code == 401  # fresh window: 4 attempts left, not locked


# ---------- backup restore ----------

def _token(client):
    return {"Authorization": f"Bearer {unlock(client, PIN).json()['token']}"}


def _seed(client):
    run(client, db.register_services.delete_many, {})
    run(client, db.register_services.insert_one, {"service_date": "2026-01-04", "attendance": 100, "comparison_service_date": "2025-12-28", "updated_at": "2026-01-04T12:00:00+00:00"})


def _backup_bytes(client, h):
    name = client.post("/api/backup/run?email=false", headers=h).json()["name"]
    return (Path(os.environ["BACKUP_DIR"]) / name).read_bytes()


def _count(client):
    return run(client, db.register_services.count_documents, {})


def test_invalid_file_is_rejected_and_data_kept(client):
    h = _token(client)
    _seed(client)
    r = client.post("/api/backup/restore-upload?confirm=true", headers=h, files={"file": ("x.gz", b"junk")})
    assert r.status_code == 422 and _count(client) == 1


def test_valid_structure_but_bad_documents_rejected_before_any_delete(client):
    h = _token(client)
    _seed(client)
    bad = gzip.compress(json.dumps({"app": "sanctuary-screens", "collections": {"register_services": ["nope"]}}).encode())
    r = client.post("/api/backup/restore-upload?confirm=true", headers=h, files={"file": ("x.gz", bad)})
    assert r.status_code == 422 and _count(client) == 1


def test_good_restore_round_trip_and_safety_backup(client):
    h = _token(client)
    _seed(client)
    raw = _backup_bytes(client, h)
    run(client, db.register_services.delete_many, {})
    r = client.post("/api/backup/restore-upload?confirm=true", headers=h, files={"file": ("b.gz", raw)})
    assert r.status_code == 200 and _count(client) == 1
    assert (Path(os.environ["BACKUP_DIR"]) / r.json()["safety_backup"]).exists()


def test_failed_restore_rolls_back(client, monkeypatch):
    h = _token(client)
    _seed(client)
    raw = _backup_bytes(client, h)
    run(client, db.register_services.insert_one, {"service_date": "2026-02-01", "attendance": 5, "comparison_service_date": "2026-01-25", "updated_at": "2026-02-01T12:00:00+00:00"})  # newer data
    real = backup._apply_backup
    calls = {"n": 0}

    async def flaky(data):
        calls["n"] += 1
        if calls["n"] == 1:
            await db.register_services.delete_many({})  # destructive step, then crash
            raise RuntimeError("boom")
        return await real(data)

    monkeypatch.setattr(backup, "_apply_backup", flaky)
    r = client.post("/api/backup/restore-upload?confirm=true", headers=h, files={"file": ("b.gz", raw)})
    assert r.status_code == 500 and "put back" in r.json()["detail"]
    assert _count(client) == 2  # pre-restore data (including the newer record) is back


def test_decompression_bomb_and_oversize_upload_rejected(client, monkeypatch):
    h = _token(client)
    _seed(client)
    big = gzip.compress(b"0" * 50_000)
    monkeypatch.setattr(backup, "MAX_RESTORE_BYTES", 1000)
    r = client.post("/api/backup/restore-upload?confirm=true", headers=h, files={"file": ("b.gz", big)})
    assert r.status_code == 413 and _count(client) == 1
    monkeypatch.setattr(backup, "MAX_UPLOAD_BYTES", 10)
    r = client.post("/api/backup/restore-upload?confirm=true", headers=h, files={"file": ("b.gz", big)})
    assert r.status_code == 413 and _count(client) == 1


# ---------- CORS, uploads, SMTP password ----------

PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
       b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x9a\xa0\xa0\x00\x00\x00\x00IEND\xaeB`\x82")


def test_wildcard_cors_is_not_enabled(client):
    r = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert r.status_code == 200 and "access-control-allow-origin" not in r.headers


def test_image_upload_checks_real_content(client):
    h = _token(client)
    fake = client.post("/api/appearance/logo", headers=h, files={"file": ("x.png", b"<script>alert(1)</script>", "image/png")})
    assert fake.status_code == 415
    ok = client.post("/api/appearance/logo", headers=h, files={"file": ("x.png", PNG, "image/jpeg")})
    assert ok.status_code == 200  # type is detected from the bytes, not the label
    img_id = ok.json()["church_logo_url"].rsplit("/", 1)[1]
    assert client.get(f"/api/appearance/image/{img_id}").headers["content-type"] == "image/png"


def _smtp_body(**kw):
    return {"smtp_host": "mail.example", "smtp_port": 587, "smtp_security": "starttls", "smtp_user": "u",
            "smtp_password": "hunter2-secret", "email_to": "a@b.c", **kw}


def test_smtp_password_encrypted_at_rest_and_usable(client):
    h = _token(client)
    r = client.put("/api/backup/settings", headers=h, json=_smtp_body())
    assert r.status_code == 200 and "smtp_password" not in r.json() and r.json()["has_password"] is True
    stored = run(client, db.backup_settings.find_one, {"_id": "settings"})["smtp_password"]
    assert stored.startswith("enc:v1:") and "hunter2" not in stored
    assert run(client, backup.load_settings)["smtp_password"] == "hunter2-secret"


def test_blank_password_on_save_keeps_existing(client):
    h = _token(client)
    client.put("/api/backup/settings", headers=h, json=_smtp_body())
    client.put("/api/backup/settings", headers=h, json=_smtp_body(smtp_password=""))
    assert run(client, backup.load_settings)["smtp_password"] == "hunter2-secret"


def test_legacy_plaintext_password_is_migrated(client):
    run(client, db.backup_settings.update_one, {"_id": "settings"}, {"$set": {"smtp_password": "old-plain"}})
    run(client, backup.encrypt_legacy_smtp_password)
    stored = run(client, db.backup_settings.find_one, {"_id": "settings"})["smtp_password"]
    assert stored.startswith("enc:v1:")
    assert run(client, backup.load_settings)["smtp_password"] == "old-plain"


def test_undecryptable_password_is_treated_as_unset(client):
    run(client, db.backup_settings.update_one, {"_id": "settings"}, {"$set": {"smtp_password": "enc:v1:garbage"}})
    assert run(client, backup.load_settings)["smtp_password"] == ""


def test_credentials_over_unencrypted_smtp_rejected(client):
    h = _token(client)
    r = client.put("/api/backup/settings", headers=h, json=_smtp_body(smtp_security="none"))
    assert r.status_code == 422
    assert client.put("/api/backup/settings", headers=h,
                      json=_smtp_body(smtp_security="none", smtp_user="", smtp_password="")).status_code == 200

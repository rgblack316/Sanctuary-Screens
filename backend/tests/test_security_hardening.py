"""Offline tests for the security hardening (PIN lockout, secrets, backup restore).

Runs against an in-memory MongoDB stand-in, so no running stack is needed:
    pip install mongomock-motor httpx pytest
    cd backend && python -m pytest tests/test_security_hardening.py -n 0
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

pytest.importorskip("mongomock_motor")
pytest.importorskip("httpx")

BACKEND = Path(__file__).resolve().parent.parent
PIN = "4821"
STRONG = "a" * 64
_tmp = tempfile.mkdtemp()

os.environ.update(MONGO_URL="mongodb://mock", DB_NAME="hardening_test", ADMIN_PIN=PIN, JWT_SECRET=STRONG,
                  SEED_DIR=_tmp, BACKUP_DIR=os.path.join(_tmp, "backups"), IDLE_ASSET_DIR=_tmp)
sys.path.insert(0, str(BACKEND))

import motor.motor_asyncio as _motor  # noqa: E402
from mongomock_motor import AsyncMongoMockClient  # noqa: E402

_motor.AsyncIOMotorClient = AsyncMongoMockClient

import jwt  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import backup  # noqa: E402
import server  # noqa: E402
from core import JWT_ALG, JWT_SECRET, db  # noqa: E402


@pytest.fixture(autouse=True)
def clean(client):
    client.portal.call(db.pin_attempts.delete_many, {})
    yield


@pytest.fixture(scope="module")
def client():
    with TestClient(server.app) as c:
        yield c


def unlock(client, pin, area="settings"):
    return client.post("/api/auth/unlock", json={"pin": pin, "area": area})


def run(client, coro_fn, *a):
    return client.portal.call(coro_fn, *a)


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

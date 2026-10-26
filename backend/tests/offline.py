"""Shared bootstrap for the offline tests: in-memory MongoDB stand-in, env, app and helpers."""
import os
import sys
import tempfile
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

import jwt  # noqa: E402,F401
from fastapi.testclient import TestClient  # noqa: E402

import backup  # noqa: E402,F401
import server  # noqa: E402
from core import JWT_ALG, JWT_SECRET, db  # noqa: E402,F401




@pytest.fixture(scope="module")
def client():
    with TestClient(server.app) as c:
        yield c


def run(client, coro_fn, *a):
    return client.portal.call(coro_fn, *a)


def unlock(client, pin=PIN, area="bible"):
    return client.post("/api/auth/unlock", json={"pin": pin, "area": area})


def auth(client, area="bible"):
    return {"Authorization": f"Bearer {unlock(client, PIN, area).json()['token']}"}

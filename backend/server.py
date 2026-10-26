import asyncio
import hashlib
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Literal

import bcrypt
import jwt
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from fastapi import APIRouter, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

import appearance_routes
import backup
import bible_routes
import library_routes
import looks_routes
from core import (ADMIN_PIN, BIBLE_AUTH, ENV_JWT_SECRET, JWT_ALG, JWT_SECRET, REGISTER_AUTH, SEED_DIR, SESSION_HOURS, SETTINGS_AUTH,
                  client, db, hub, now_iso)
from importer import validate_csv
from register_routes import register_state, router as register_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("sanctuary")

MAX_ATTEMPTS = 5
LOCK_MINUTES = 5
MAX_LOCK_MINUTES = 24 * 60
MAX_WS_PER_CHANNEL = 100

app = FastAPI(title="Sanctuary Screens")
api = APIRouter(prefix="/api")


# ---------- auth ----------

class UnlockIn(BaseModel):
    pin: str
    area: Literal["register", "bible", "settings"]


class ChangePinIn(BaseModel):
    current_pin: str
    new_pin: str


def client_ip(request: Request) -> str:
    # uvicorn --proxy-headers only honours X-Forwarded-For from the local nginx (127.0.0.1),
    # so request.client is the real client address. Never read the raw header: a client
    # talking to the backend directly could spoof it to dodge the PIN lockout.
    return request.client.host if request.client else "unknown"


async def _claim_attempt(ip: str, now_iso_str: str) -> dict:
    """Atomically count one PIN attempt for this IP and return the updated record.

    The counter is incremented *before* the PIN is checked, in a single database operation, so a
    burst of simultaneous guesses cannot all read "0 attempts so far" and slip past the limit.
    """
    now = datetime.fromisoformat(now_iso_str)
    # Quiet for a day: forget the IP completely (strike history included).
    await db.pin_attempts.delete_one({"_id": ip, "updated_at": {"$lt": (now - timedelta(hours=24)).isoformat()}})
    # An expired lock starts a fresh window (strikes are kept so repeat offenders wait longer).
    await db.pin_attempts.update_one({"_id": ip, "locked_until": {"$ne": None, "$lte": now_iso_str}},
                                     {"$set": {"count": 0, "locked_until": None}})
    # A few stray typos long ago should not count towards today's allowance.
    await db.pin_attempts.update_one({"_id": ip, "locked_until": None,
                                      "updated_at": {"$lt": (now - timedelta(minutes=15)).isoformat()}},
                                     {"$set": {"count": 0}})
    for _ in range(3):
        try:
            return await db.pin_attempts.find_one_and_update(
                {"_id": ip}, {"$inc": {"count": 1}, "$set": {"updated_at": now_iso_str}, "$setOnInsert": {"locked_until": None, "strikes": 0}},
                upsert=True, return_document=ReturnDocument.AFTER)
        except DuplicateKeyError:  # two first-ever attempts raced to create the record; retry
            continue
    raise HTTPException(503, "Please try again.")


async def _lock(ip: str) -> int:
    """Lock this IP. Each repeated lockout doubles the wait (5, 10, 20 ... minutes, max 24 h)."""
    rec = await db.pin_attempts.find_one_and_update(
        {"_id": ip, "locked_until": None}, {"$inc": {"strikes": 1}}, return_document=ReturnDocument.AFTER)
    strikes = (rec or {}).get("strikes", 1)
    minutes = min(LOCK_MINUTES * 2 ** max(0, strikes - 1), MAX_LOCK_MINUTES)
    until = (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()
    await db.pin_attempts.update_one({"_id": ip, "locked_until": None}, {"$set": {"locked_until": until}})
    return minutes


def _lock_message(locked_until: str, now: datetime) -> str:
    secs = (datetime.fromisoformat(locked_until) - now).total_seconds()
    mins = max(1, int(secs // 60) + 1)
    return f"Too many incorrect attempts. Try again in {mins} minute(s)."


async def check_pin(pin: str, request: Request) -> dict:
    """Verify the PIN with per-IP lockout. Returns the admin config on success."""
    ip = client_ip(request)
    now = datetime.now(timezone.utc)
    rec = await _claim_attempt(ip, now.isoformat())
    if rec.get("locked_until"):
        raise HTTPException(429, _lock_message(rec["locked_until"], now))
    if rec["count"] > MAX_ATTEMPTS:  # beyond the allowance within one window (e.g. a parallel burst)
        await _lock(ip)
        rec = await db.pin_attempts.find_one({"_id": ip}) or {}
        raise HTTPException(429, _lock_message(rec["locked_until"], now) if rec.get("locked_until")
                            else "Too many incorrect attempts. Try again later.")
    cfg = await db.admin_config.find_one({"_id": "admin"})
    valid = bool(re.fullmatch(r"\d{4}", pin)) and bcrypt.checkpw(pin.encode(), cfg["pin_hash"].encode())
    if not valid:
        if rec["count"] >= MAX_ATTEMPTS:
            minutes = await _lock(ip)
            raise HTTPException(429, f"Too many incorrect attempts. Try again in {minutes} minutes.")
        raise HTTPException(401, f"Incorrect PIN. {MAX_ATTEMPTS - rec['count']} attempt(s) left.")
    await db.pin_attempts.delete_one({"_id": ip})
    return cfg


def issue_token(area: str, cfg: dict) -> dict:
    exp = datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS)
    token = jwt.encode({"area": area, "pv": cfg.get("pin_version", 1), "exp": exp}, JWT_SECRET, algorithm=JWT_ALG)
    return {"token": token, "area": area, "expires_at": exp.isoformat()}


@api.post("/auth/unlock")
async def unlock(body: UnlockIn, request: Request):
    return issue_token(body.area, await check_pin(body.pin, request))


@api.post("/auth/change-pin", dependencies=[SETTINGS_AUTH])
async def change_pin(body: ChangePinIn, request: Request):
    if not re.fullmatch(r"\d{4}", body.new_pin):
        raise HTTPException(422, "New PIN must be exactly 4 digits.")
    cfg = await check_pin(body.current_pin, request)
    if body.new_pin == body.current_pin:
        raise HTTPException(422, "New PIN must be different from the current PIN.")
    version = cfg.get("pin_version", 1) + 1
    await db.admin_config.update_one({"_id": "admin"}, {"$set": {
        "pin_hash": bcrypt.hashpw(body.new_pin.encode(), bcrypt.gensalt()).decode(),
        "pin_version": version, "pin_source": "admin_ui", "updated_at": now_iso()}})
    log.info("Admin PIN changed from the settings panel")
    return issue_token("settings", {"pin_version": version})


@api.get("/auth/check/register", dependencies=[REGISTER_AUTH])
async def check_register():
    return {"ok": True}


@api.get("/auth/check/bible", dependencies=[BIBLE_AUTH])
async def check_bible():
    return {"ok": True}


@api.get("/auth/check/settings", dependencies=[SETTINGS_AUTH])
async def check_settings():
    return {"ok": True}


@api.get("/health")
async def health():
    await db.command("ping")
    meta = await db.app_meta.find_one({"_id": "schema"}) or {}
    return {"status": "ok", "db": "ok", "schema_version": meta.get("version", 0),
            "translations": await db.bible_translations.count_documents({"import_status": "ready"})}


api.include_router(register_router)
api.include_router(bible_routes.router)
api.include_router(library_routes.router)
api.include_router(appearance_routes.router)
api.include_router(looks_routes.router)
api.include_router(backup.router)
app.include_router(api)

STATE_FN = {"register": register_state, "bible": bible_routes.bible_state}


@app.websocket("/api/ws/{channel}")
async def ws_endpoint(ws: WebSocket, channel: str):
    if channel not in hub.channels:
        await ws.close(code=4404)
        return
    if len(hub.channels[channel]) >= MAX_WS_PER_CHANNEL:  # displays are a handful of screens, not hundreds
        await ws.close(code=1013)
        return
    await hub.connect(channel, ws)
    try:
        await ws.send_text(json.dumps({"type": "state", "data": await STATE_FN[channel]()}))
        while True:
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_text('{"type":"pong"}')
            elif msg == "sync":
                await ws.send_text(json.dumps({"type": "state", "data": await STATE_FN[channel]()}))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.info("ws %s closed: %s", channel, e)
    finally:
        hub.drop(channel, ws)


# The browser always talks to the app through nginx on one origin, so CORS is not needed in production.
# Only an explicit list of origins (for a separate dev server) enables it; "*" is deliberately ignored,
# otherwise any web page open on a LAN device could call the API.
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip() and o.strip() != "*"]
if CORS_ORIGINS:
    app.add_middleware(CORSMiddleware, allow_credentials=False, allow_origins=CORS_ORIGINS,
                       allow_methods=["*"], allow_headers=["*"])


# ---------- startup: indexes, migrations, PIN, seed ----------

async def ensure_indexes():
    await db.register_services.create_index("service_date", unique=True)
    await db.bible_verses.create_index([("translation_code", 1), ("book_normalized", 1), ("chapter", 1), ("verse", 1)])
    await db.bible_verses.create_index([("translation_code", 1), ("reference_key", 1)])
    await db.bible_translations.create_index("translation_code", unique=True)
    await db.bible_prepared.create_index([("service_date", 1), ("sort_order", 1)])
    await db.bible_passages.create_index("status")


async def migrate_v1():
    await db.bible_verses.delete_many({"translation_code": {"$regex": "^__staging__"}})


MIGRATIONS = {1: migrate_v1}


async def run_migrations():
    meta = await db.app_meta.find_one({"_id": "schema"}) or {}
    current = meta.get("version", 0)
    for v in sorted(k for k in MIGRATIONS if k > current):
        log.info("Running migration v%s", v)
        await MIGRATIONS[v]()
        await db.app_meta.update_one({"_id": "schema"}, {"$set": {"version": v, "updated_at": now_iso()}}, upsert=True)


async def ensure_pin():
    """ADMIN_PIN seeds the PIN; later it only applies again if its value in .env is changed."""
    fingerprint = hashlib.sha256(f"{ENV_JWT_SECRET}:{ADMIN_PIN}".encode()).hexdigest()
    cfg = await db.admin_config.find_one({"_id": "admin"})
    if cfg and cfg.get("env_pin_fingerprint") == fingerprint:
        return
    update = {"env_pin_fingerprint": fingerprint}
    if not cfg or not bcrypt.checkpw(ADMIN_PIN.encode(), cfg["pin_hash"].encode()):
        update.update(pin_hash=bcrypt.hashpw(ADMIN_PIN.encode(), bcrypt.gensalt()).decode(),
                      pin_version=(cfg or {}).get("pin_version", 0) + 1, pin_source="env", updated_at=now_iso())
        log.info("Admin PIN set from ADMIN_PIN")
    await db.admin_config.update_one({"_id": "admin"}, {"$set": update}, upsert=True)


async def seed_translations():
    if await db.bible_translations.count_documents({"import_status": "ready"}) > 0 or not SEED_DIR.is_dir():
        return
    manifest_path = SEED_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for path in sorted(SEED_DIR.glob("*.csv")):
        report, rows = validate_csv(path.read_bytes())
        if not report["ok"]:
            log.error("Seed %s failed validation: %s", path.name, report["errors"][:3])
            continue
        t = await bible_routes.commit_import(rows, report, manifest.get(path.name, {}).get("name", ""), path.name, False)
        log.info("Seeded translation %s (%s verses)", t.translation_code, t.verse_count)
    code = await bible_routes.default_translation()
    await db.bible_settings.update_one({"_id": "settings"}, {"$set": {"default_translation": code}}, upsert=True)


@app.on_event("startup")
async def startup():
    await ensure_indexes()
    await run_migrations()
    await ensure_pin()
    await backup.encrypt_legacy_smtp_password()
    asyncio.create_task(seed_translations())
    asyncio.create_task(backup.scheduler_loop())


@app.on_event("shutdown")
async def shutdown():
    client.close()

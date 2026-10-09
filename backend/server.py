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
from fastapi import APIRouter, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

import appearance_routes
import bible_routes
from core import (ADMIN_PIN, BIBLE_AUTH, JWT_ALG, JWT_SECRET, REGISTER_AUTH, SEED_DIR, SESSION_HOURS, SETTINGS_AUTH,
                  client, db, hub, now_iso)
from importer import validate_csv
from register_routes import register_state, router as register_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("sanctuary")

MAX_ATTEMPTS = 5
LOCK_MINUTES = 5

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
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")


async def check_pin(pin: str, request: Request) -> dict:
    """Verify the PIN with per-IP lockout. Returns the admin config on success."""
    ip = client_ip(request)
    now = datetime.now(timezone.utc)
    rec = await db.pin_attempts.find_one({"_id": ip}) or {}
    if rec.get("locked_until") and rec["locked_until"] > now.isoformat():
        mins = max(1, int((datetime.fromisoformat(rec["locked_until"]) - now).total_seconds() // 60) + 1)
        raise HTTPException(429, f"Too many incorrect attempts. Try again in {mins} minute(s).")
    cfg = await db.admin_config.find_one({"_id": "admin"})
    valid = bool(re.fullmatch(r"\d{4}", pin)) and bcrypt.checkpw(pin.encode(), cfg["pin_hash"].encode())
    if not valid:
        count = rec.get("count", 0) + 1
        if count >= MAX_ATTEMPTS:
            update = {"count": 0, "locked_until": (now + timedelta(minutes=LOCK_MINUTES)).isoformat()}
            await db.pin_attempts.update_one({"_id": ip}, {"$set": update}, upsert=True)
            raise HTTPException(429, f"Too many incorrect attempts. Try again in {LOCK_MINUTES} minutes.")
        await db.pin_attempts.update_one({"_id": ip}, {"$set": {"count": count, "locked_until": None}}, upsert=True)
        raise HTTPException(401, f"Incorrect PIN. {MAX_ATTEMPTS - count} attempt(s) left.")
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
api.include_router(appearance_routes.router)
app.include_router(api)

STATE_FN = {"register": register_state, "bible": bible_routes.bible_state}


@app.websocket("/api/ws/{channel}")
async def ws_endpoint(ws: WebSocket, channel: str):
    if channel not in hub.channels:
        await ws.close(code=4404)
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


app.add_middleware(
    CORSMiddleware,
    allow_credentials=False,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    fingerprint = hashlib.sha256(f"{JWT_SECRET}:{ADMIN_PIN}".encode()).hexdigest()
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
    asyncio.create_task(seed_translations())


@app.on_event("shutdown")
async def shutdown():
    client.close()

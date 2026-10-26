import json
import logging
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorClient

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]

log = logging.getLogger("sanctuary.core")

ADMIN_PIN = os.environ["ADMIN_PIN"]
# Raw .env value: only used for the PIN fingerprint in server.ensure_pin (kept unchanged so existing
# installs never have their PIN reset by this hardening).
ENV_JWT_SECRET = os.environ["JWT_SECRET"]
WEAK_SECRETS = {"", "change-me", "changeme", "secret", "password"}
WEAK_PINS = {"1234", "0000", "1111", "2222", "3333", "4444", "5555", "6666", "7777", "8888", "9999",
             "4321", "1212", "2580", "1004", "2000"}

# A placeholder or short signing secret would let anyone on the LAN forge admin sessions. Instead of
# refusing to start (the displays must keep working), fall back to a random per-boot secret: admin
# sessions then end whenever the backend restarts, until a real secret is set in .env.
if ENV_JWT_SECRET.strip().lower() in WEAK_SECRETS or len(ENV_JWT_SECRET) < 32:
    JWT_SECRET = secrets.token_hex(32)
    log.warning("JWT_SECRET in .env is a placeholder or shorter than 32 characters; using a random "
                "per-boot secret. Admin sessions will reset on every restart. Fix: set JWT_SECRET to "
                "the output of `openssl rand -hex 32` in .env, then `docker compose up -d`.")
else:
    JWT_SECRET = ENV_JWT_SECRET
CURRENCY = os.environ.get("CURRENCY_SYMBOL", "$")
IDLE_TITLE = os.environ.get("IDLE_TITLE", "Welcome")
IDLE_SUBTITLE = os.environ.get("IDLE_SUBTITLE", "")
IDLE_DIR = Path(os.environ.get("IDLE_ASSET_DIR", str(ROOT_DIR / "data" / "idle")))
SEED_DIR = Path(os.environ.get("SEED_DIR", str(ROOT_DIR / "seed")))
SESSION_HOURS = 12
MAX_SLIDES = 300
JWT_ALG = "HS256"

if not re.fullmatch(r"\d{4}", ADMIN_PIN):
    raise RuntimeError("ADMIN_PIN must be exactly 4 digits")
if ADMIN_PIN in WEAK_PINS:
    log.warning("ADMIN_PIN in .env is a common PIN (%s). Change it in /settings-admin > Admin PIN.", ADMIN_PIN)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Hub:
    def __init__(self):
        self.channels = {"register": set(), "bible": set()}

    async def connect(self, channel, ws):
        await ws.accept()
        self.channels[channel].add(ws)

    def drop(self, channel, ws):
        self.channels[channel].discard(ws)

    async def broadcast(self, channel, data):
        msg = json.dumps({"type": "state", "data": data})
        for ws in list(self.channels[channel]):
            try:
                await ws.send_text(msg)
            except Exception:
                self.drop(channel, ws)


hub = Hub()


def _require_area(area: str):
    async def dep(request: Request):
        auth = request.headers.get("Authorization", "")
        token = auth[7:] if auth.startswith("Bearer ") else None
        if not token:
            raise HTTPException(401, "PIN required")
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG], options={"require": ["exp"]})
        except jwt.InvalidTokenError:
            raise HTTPException(401, "Session expired. Enter the PIN again.")
        if payload.get("area") != area:
            raise HTTPException(401, "PIN required for this admin area")
        cfg = await db.admin_config.find_one({"_id": "admin"}, {"pin_version": 1}) or {}
        if payload.get("pv") != cfg.get("pin_version", 1):
            raise HTTPException(401, "The PIN was changed. Enter the new PIN.")
        return payload
    return dep


REGISTER_AUTH = Depends(_require_area("register"))
BIBLE_AUTH = Depends(_require_area("bible"))
SETTINGS_AUTH = Depends(_require_area("settings"))

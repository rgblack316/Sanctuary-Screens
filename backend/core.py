import json
import os
import re
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

ADMIN_PIN = os.environ["ADMIN_PIN"]
JWT_SECRET = os.environ["JWT_SECRET"]
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
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        except jwt.InvalidTokenError:
            raise HTTPException(401, "Session expired. Enter the PIN again.")
        if payload.get("area") != area:
            raise HTTPException(401, "PIN required for this admin area")
        return payload
    return dep


REGISTER_AUTH = Depends(_require_area("register"))
BIBLE_AUTH = Depends(_require_area("bible"))

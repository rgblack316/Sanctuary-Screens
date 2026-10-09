import asyncio
import gzip
import logging
import os
import re
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Literal

from bson import json_util
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from core import ROOT_DIR, SETTINGS_AUTH, db, hub, now_iso

log = logging.getLogger("sanctuary.backup")
router = APIRouter(prefix="/backup", dependencies=[SETTINGS_AUTH])
BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", str(ROOT_DIR / "backups")))
NAME_RE = re.compile(r"^sanctuary-backup-\d{8}-\d{6}\.json\.gz$")
COLLECTIONS = ["register_services", "register_state", "bible_translations", "bible_verses", "bible_prepared",
               "bible_settings", "display_appearance", "display_looks", "display_images", "site_settings"]
MAX_ATTACH = 20 * 1024 * 1024


class BackupSettingsIn(BaseModel):
    schedule_enabled: bool = True
    weekday: int = Field(6, ge=0, le=6)
    time: str = Field("23:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    keep: int = Field(8, ge=1, le=100)
    email_enabled: bool = False
    smtp_host: str = Field("", max_length=200)
    smtp_port: int = Field(587, ge=1, le=65535)
    smtp_security: Literal["starttls", "ssl", "none"] = "starttls"
    smtp_user: str = Field("", max_length=200)
    smtp_password: str = Field("", max_length=300)
    email_from: str = Field("", max_length=200)
    email_to: str = Field("", max_length=500)


async def load_settings() -> dict:
    doc = await db.backup_settings.find_one({"_id": "settings"}) or {}
    data = BackupSettingsIn(**{k: doc[k] for k in BackupSettingsIn.model_fields if k in doc}).model_dump()
    data.update(last_run=doc.get("last_run"), last_auto_date=doc.get("last_auto_date"))
    return data


def _public(s: dict) -> dict:
    out = {k: v for k, v in s.items() if k != "smtp_password"}
    out["has_password"] = bool(s.get("smtp_password"))
    return out


def _files() -> list:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return sorted((p for p in BACKUP_DIR.iterdir() if NAME_RE.match(p.name)), key=lambda p: p.name, reverse=True)


def _path(name: str) -> Path:
    p = BACKUP_DIR / name
    if not NAME_RE.match(name) or not p.exists():
        raise HTTPException(404, "Backup not found")
    return p


def _send_email(s: dict, path: Path, note: str = ""):
    msg = EmailMessage()
    msg["Subject"] = f"Sanctuary Screens backup {path.name[18:33]}" if path else "Sanctuary Screens test email"
    msg["From"] = s["email_from"] or s["smtp_user"]
    msg["To"] = s["email_to"]
    if path and path.stat().st_size <= MAX_ATTACH:
        msg.set_content(f"Attached is the latest Sanctuary Screens backup ({path.name}). {note}")
        msg.add_attachment(path.read_bytes(), maintype="application", subtype="gzip", filename=path.name)
    elif path:
        msg.set_content(f"Backup {path.name} was created but is too large to attach. It is stored on the NUC in the backups folder.")
    else:
        msg.set_content("Email settings for Sanctuary Screens backups are working.")
    ctx = ssl.create_default_context()
    if s["smtp_security"] == "ssl":
        server = smtplib.SMTP_SSL(s["smtp_host"], s["smtp_port"], context=ctx, timeout=30)
    else:
        server = smtplib.SMTP(s["smtp_host"], s["smtp_port"], timeout=30)
        if s["smtp_security"] == "starttls":
            server.starttls(context=ctx)
    with server:
        if s["smtp_user"]:
            server.login(s["smtp_user"], s["smtp_password"])
        server.send_message(msg)


def _email_ready(s: dict) -> bool:
    return bool(s["email_enabled"] and s["smtp_host"] and s["email_to"])


async def create_backup(send_email: bool, trigger: str) -> dict:
    data = {"app": "sanctuary-screens", "version": 1, "created_at": now_iso(), "collections": {}}
    for c in COLLECTIONS:
        data["collections"][c] = await db[c].find().to_list(None)
    raw = gzip.compress(json_util.dumps(data).encode())
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    path = BACKUP_DIR / f"sanctuary-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json.gz"
    path.write_bytes(raw)
    s = await load_settings()
    for old in _files()[s["keep"]:]:
        old.unlink(missing_ok=True)
    result = {"name": path.name, "size": len(raw), "trigger": trigger, "at": now_iso(), "emailed": False, "email_error": None}
    if send_email and _email_ready(s):
        try:
            await asyncio.to_thread(_send_email, s, path)
            result["emailed"] = True
        except Exception as e:
            result["email_error"] = str(e)
            log.error("Backup email failed: %s", e)
    await db.backup_settings.update_one({"_id": "settings"}, {"$set": {"last_run": result}}, upsert=True)
    return result


async def restore_bytes(raw: bytes) -> dict:
    try:
        data = json_util.loads(gzip.decompress(raw).decode())
        assert data.get("app") == "sanctuary-screens"
    except Exception:
        raise HTTPException(422, "This is not a valid Sanctuary Screens backup file.")
    counts = {}
    for c in COLLECTIONS:
        docs = data["collections"].get(c)
        if docs is None:
            continue
        await db[c].delete_many({})
        if docs:
            await db[c].insert_many(docs)
        counts[c] = len(docs)
    from bible_routes import _books_cache, bible_state
    from register_routes import register_state
    _books_cache.clear()
    await db.bible_display.update_one({"_id": "state"}, {"$set": {"mode": "idle", "active_passage_id": None}}, upsert=True)
    await hub.broadcast("register", await register_state())
    await hub.broadcast("bible", await bible_state())
    return {"restored": counts, "backup_created_at": data.get("created_at")}


async def scheduler_loop():
    while True:
        await asyncio.sleep(60)
        try:
            s = await load_settings()
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")
            if (s["schedule_enabled"] and now.weekday() == s["weekday"] and now.strftime("%H:%M") >= s["time"]
                    and s.get("last_auto_date") != today):
                await db.backup_settings.update_one({"_id": "settings"}, {"$set": {"last_auto_date": today}}, upsert=True)
                await create_backup(True, "scheduled")
                log.info("Scheduled backup created")
        except Exception as e:
            log.error("Scheduled backup failed: %s", e)


@router.get("/settings")
async def get_settings():
    return _public(await load_settings())


@router.put("/settings")
async def put_settings(body: BackupSettingsIn):
    data = body.model_dump()
    if not data["smtp_password"]:
        data.pop("smtp_password")
    await db.backup_settings.update_one({"_id": "settings"}, {"$set": data}, upsert=True)
    return _public(await load_settings())


@router.post("/test-email")
async def test_email():
    s = await load_settings()
    if not (s["smtp_host"] and s["email_to"]):
        raise HTTPException(422, "Enter the SMTP server and recipient email first, then save.")
    try:
        await asyncio.to_thread(_send_email, s, None)
    except Exception as e:
        raise HTTPException(502, f"Email failed: {e}")
    return {"ok": True}


@router.get("/list")
async def list_backups():
    return {"backups": [{"name": p.name, "size": p.stat().st_size} for p in _files()],
            "folder": str(BACKUP_DIR), "last_run": (await load_settings()).get("last_run")}


@router.post("/run")
async def run_backup(email: bool = True):
    return await create_backup(email, "manual")


@router.get("/download/{name}")
async def download(name: str):
    return FileResponse(_path(name), media_type="application/gzip", filename=name)


@router.delete("/{name}")
async def delete_backup(name: str):
    _path(name).unlink()
    return {"deleted": name}


@router.post("/restore/{name}")
async def restore_local(name: str, confirm: bool = False):
    if not confirm:
        raise HTTPException(400, "Restore must be confirmed.")
    return await restore_bytes(_path(name).read_bytes())


@router.post("/restore-upload")
async def restore_upload(file: UploadFile = File(...), confirm: bool = False):
    if not confirm:
        raise HTTPException(400, "Restore must be confirmed.")
    return await restore_bytes(await file.read())

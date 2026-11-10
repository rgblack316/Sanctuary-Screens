"""Webhook receiver so another system (e.g. the church playout app) can drive /bible.

POST /api/hooks/bible   (Authorization: Bearer <token>  or  X-Webhook-Token: <token>)
  {"action": "next" | "prev" | "clear"}
  {"action": "goto", "index": 0}
  {"action": "clear", "only_if": "hymn"}   # back to idle only if the song sent by this webhook is still showing
  {"action": "hymn", "songbook": "Baptist Hymnal", "title": "Amazing Grace", "page": "112"}

The token is generated in /settings-admin and only its hash is stored.
"""
import hashlib
import hmac
import re
import secrets
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

import bible_routes
from core import SETTINGS_AUTH, db, now_iso
from models import PreparedItem
from songs_routes import _page_sort, _public, key

router = APIRouter(prefix="/hooks")
CFG = {"_id": "webhook"}
PREFIX = "ssw_"
HOOK_HYMN = "hook:hymn"  # marks a passage that was put on screen by the webhook


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def _config() -> dict:
    return await db.admin_config.find_one(CFG) or {}


async def require_token(authorization: str = Header(""), x_webhook_token: str = Header("")):
    token = x_webhook_token.strip() or (authorization[7:].strip() if authorization.startswith("Bearer ") else "")
    stored = (await _config()).get("token_hash")
    if not stored:
        raise HTTPException(403, "Webhook is turned off. Create a token in Settings first.")
    if not token or not hmac.compare_digest(_hash(token), stored):
        raise HTTPException(401, "Invalid webhook token.")


# ---------- token management (settings PIN) ----------

async def _public_config() -> dict:
    c = await _config()
    return {"enabled": bool(c.get("token_hash")), "token_hint": c.get("token_hint"),
            "created_at": c.get("created_at"), "log_played": c.get("log_played", True)}


@router.get("/config", dependencies=[SETTINGS_AUTH])
async def get_config():
    return await _public_config()


@router.post("/token", dependencies=[SETTINGS_AUTH])
async def create_token():
    """Create (or replace) the token. The plain token is returned once and never stored."""
    token = PREFIX + secrets.token_urlsafe(32)
    await db.admin_config.update_one(CFG, {"$set": {"token_hash": _hash(token), "token_hint": token[-4:],
                                                    "created_at": now_iso()}}, upsert=True)
    return {**await _public_config(), "token": token}


@router.delete("/token", dependencies=[SETTINGS_AUTH])
async def revoke_token():
    await db.admin_config.update_one(CFG, {"$unset": {"token_hash": "", "token_hint": "", "created_at": ""}}, upsert=True)
    return await _public_config()


class ConfigIn(BaseModel):
    log_played: bool


@router.put("/config", dependencies=[SETTINGS_AUTH])
async def put_config(body: ConfigIn):
    await db.admin_config.update_one(CFG, {"$set": {"log_played": body.log_played}}, upsert=True)
    return await _public_config()


# ---------- receiver ----------

class HookIn(BaseModel):
    action: Literal["next", "prev", "goto", "clear", "hymn"]
    index: Optional[int] = Field(None, ge=0, le=10000)
    songbook: str = Field("", max_length=80)
    title: str = Field("", max_length=160)
    page: str = Field("", max_length=12)
    only_if: Optional[Literal["hymn"]] = None


async def _find_song(body: HookIn) -> list:
    flt: dict = {}
    if body.songbook.strip():
        flt["songbook_key"] = key(body.songbook)
    if body.page.strip():
        flt["page_key"] = key(body.page)
    docs = await db.hymnal_songs.find(flt).to_list(500) if flt else []
    title = body.title.strip()
    if title and docs:
        t = key(title)
        exact = [d for d in docs if d.get("title_key") == t]
        docs = exact or [d for d in docs if t in d.get("title_key", "")] or []
    elif title:
        docs = await db.hymnal_songs.find({"title_key": key(title)}).to_list(50)
    docs.sort(key=_page_sort)
    return docs


async def _log_played(title: str, text: str) -> bool:
    """Record the song on today's Hymns list (once per service) and mark it played."""
    today = datetime.now().strftime("%Y-%m-%d")
    existing = await db.bible_prepared.find_one({"service_date": today, "kind": "hymn", "reference": title})
    if existing:
        if not existing.get("played"):
            await db.bible_prepared.update_one({"_id": existing["_id"]}, {"$set": {"played": True, "played_at": now_iso()}})
        return False
    last = await db.bible_prepared.find_one({"service_date": today}, sort=[("sort_order", -1)])
    item = PreparedItem(service_date=today, reference=title, kind="hymn", preloaded_text_optional=text,
                        sort_order=(last["sort_order"] + 1) if last else 0, played=True, played_at=now_iso())
    await db.bible_prepared.insert_one(item.to_mongo())
    return True


async def _show_hymn(body: HookIn) -> dict:
    if not (body.title.strip() or body.page.strip()):
        raise HTTPException(422, "Send a title, a page, or both.")
    matches = await _find_song(body)
    if len(matches) > 1:
        raise HTTPException(409, {"error": "More than one song matches. Send the title as well.",
                                  "matches": [_public(d) for d in matches[:10]]})
    if matches:
        song = matches[0]
        title, page, book = song["title"], song.get("page", ""), song.get("songbook", "")
    elif body.title.strip():  # not in the imported songbook: build the slide from what was sent
        song, title, page, book = None, re.sub(r"\s+", " ", body.title).strip(), body.page.strip(), body.songbook.strip()
    else:
        raise HTTPException(404, "No song found for that page. Check the songbook name or send the title too.")
    text = "\n".join(x for x in (f"Page {page}" if page else "", book) if x)
    state = await bible_routes.publish(bible_routes.PublishIn(
        reference_input=HOOK_HYMN, normalized_reference=title, source_type="custom",
        verses=[bible_routes.SlideIn(reference_label=title, verse_text=text)]))
    logged = False
    if (await _config()).get("log_played", True):
        logged = await _log_played(title, text)
    return {"state": state, "song": _public(song) if song else None, "logged": logged}


@router.post("/bible", dependencies=[Depends(require_token)])
async def bible_hook(body: HookIn):
    if body.action == "hymn":
        return await _show_hymn(body)
    if body.action == "goto":
        if body.index is None:
            raise HTTPException(422, "goto needs an index (0 is the first slide).")
        return {"state": await bible_routes._move(index=body.index)}
    if body.action == "clear":
        if body.only_if == "hymn":
            p = await bible_routes.active_passage()
            if not p or p.reference_input != HOOK_HYMN:
                return {"state": await bible_routes.bible_state(), "cleared": False}
        return {"state": await bible_routes.clear_display(), "cleared": True}
    return {"state": await bible_routes._move(delta=1 if body.action == "next" else -1)}

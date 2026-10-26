"""Preview channel: what the admin has loaded but not yet sent to the screen, shown on /bible-preview."""
from typing import List, Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from appearance import get_appearance, get_site
from bible_routes import SlideIn, idle_config
from core import BIBLE_AUTH, MAX_SLIDES, db, hub, now_iso

router = APIRouter(prefix="/preview")


async def preview_state() -> dict:
    st = await db.bible_preview.find_one({"_id": "state"}) or {}
    base = {"mode": "idle", "preview": True, "idle": idle_config(), "updated_at": st.get("updated_at"),
            "appearance": await get_appearance("bible"), **(await get_site())}
    verses = st.get("verses") or []
    if not verses:
        return base
    idx = max(0, min(st.get("slide_index", 0), len(verses) - 1))
    code = st.get("translation_code")
    t = await db.bible_translations.find_one({"translation_code": code}) if code else None
    return {**base, "mode": "passage", "reference": st.get("normalized_reference", ""), "translation_code": code,
            "translation_name": t.get("translation_name") if t else None, "source_type": st.get("source_type"),
            "slide_index": idx, "total": len(verses), "slide": verses[idx], "slides": verses}


async def broadcast_preview() -> dict:
    state = await preview_state()
    await hub.broadcast("preview", state)
    return state


class PreviewIn(BaseModel):
    normalized_reference: str = Field(..., min_length=1, max_length=200)
    translation_code: Optional[str] = None
    source_type: Literal["local_lookup", "manual", "reference_only", "custom"]
    verses: List[SlideIn] = Field(..., min_length=1, max_length=MAX_SLIDES)
    slide_index: int = 0


class IndexIn(BaseModel):
    index: int


@router.get("/display")
async def get_preview():
    return await preview_state()


@router.put("", dependencies=[BIBLE_AUTH])
async def set_preview(body: PreviewIn):
    await db.bible_preview.update_one({"_id": "state"}, {"$set": {
        "normalized_reference": body.normalized_reference.strip(),
        "translation_code": None if body.source_type in ("custom", "manual") else body.translation_code,
        "source_type": body.source_type, "verses": [v.model_dump() for v in body.verses],
        "slide_index": max(0, min(body.slide_index, len(body.verses) - 1)), "updated_at": now_iso()}}, upsert=True)
    return await broadcast_preview()


@router.post("/index", dependencies=[BIBLE_AUTH])
async def set_index(body: IndexIn):
    await db.bible_preview.update_one({"_id": "state"}, {"$set": {"slide_index": max(0, body.index), "updated_at": now_iso()}},
                                      upsert=True)
    return await broadcast_preview()


@router.delete("", dependencies=[BIBLE_AUTH])
async def clear_preview():
    await db.bible_preview.update_one({"_id": "state"}, {"$set": {"verses": [], "slide_index": 0, "updated_at": now_iso()}},
                                      upsert=True)
    return await broadcast_preview()

import re
from typing import Literal, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core import BIBLE_AUTH, db, now_iso
from models import BaseDocument

router = APIRouter(prefix="/bible", dependencies=[BIBLE_AUTH])


class LibraryItem(BaseDocument):
    name: str
    kind: str = "scripture"
    reference: str
    translation_code: Optional[str] = None
    preloaded_text_optional: str = ""
    reference_only: bool = False
    created_at: str


class LibraryIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    kind: Literal["scripture", "custom"] = "scripture"
    reference: str = Field(..., min_length=1, max_length=200)
    translation_code: Optional[str] = None
    preloaded_text_optional: str = Field("", max_length=20000)
    reference_only: bool = False


class Hymnal(BaseDocument):
    name: str


class HymnalIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)


class LastHymnalIn(BaseModel):
    name: str = Field("", max_length=80)


def _oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise HTTPException(404, "Not found")


def _ci(name: str) -> dict:
    return {"$regex": f"^{re.escape(name)}$", "$options": "i"}


@router.get("/library")
async def list_library():
    docs = await db.bible_library.find().sort("name", 1).to_list(None)
    return {"items": [LibraryItem.from_mongo(d).model_dump() for d in docs]}


@router.post("/library")
async def create_library_item(body: LibraryIn):
    name = body.name.strip()
    if await db.bible_library.find_one({"name": _ci(name)}):
        raise HTTPException(409, f"A library slide named '{name}' already exists.")
    item = LibraryItem(**{**body.model_dump(), "name": name}, created_at=now_iso())
    res = await db.bible_library.insert_one(item.to_mongo())
    item.id = str(res.inserted_id)
    return item.model_dump()


@router.put("/library/{item_id}")
async def update_library_item(item_id: str, body: LibraryIn):
    name = body.name.strip()
    if not await db.bible_library.find_one({"_id": _oid(item_id)}):
        raise HTTPException(404, "Library slide not found")
    if await db.bible_library.find_one({"name": _ci(name), "_id": {"$ne": _oid(item_id)}}):
        raise HTTPException(409, f"A library slide named '{name}' already exists.")
    fields = {**body.model_dump(), "name": name}
    await db.bible_library.update_one({"_id": _oid(item_id)}, {"$set": fields})
    content = {k: v for k, v in fields.items() if k != "name"}
    res = await db.bible_prepared.update_many({"library_id": item_id}, {"$set": {**content, "title_or_note": name}})
    item = LibraryItem.from_mongo(await db.bible_library.find_one({"_id": _oid(item_id)}))
    return {**item.model_dump(), "prepared_updated": res.modified_count}


@router.delete("/library/{item_id}")
async def delete_library_item(item_id: str):
    if not (await db.bible_library.delete_one({"_id": _oid(item_id)})).deleted_count:
        raise HTTPException(404, "Library slide not found")
    return {"deleted": item_id}


@router.get("/hymnals")
async def list_hymnals():
    docs = await db.bible_hymnals.find().sort("name", 1).to_list(None)
    s = await db.bible_settings.find_one({"_id": "settings"}) or {}
    return {"hymnals": [Hymnal.from_mongo(d).model_dump() for d in docs], "last_used": s.get("last_hymnal") or ""}


@router.post("/hymnals")
async def create_hymnal(body: HymnalIn):
    name = body.name.strip()
    existing = Hymnal.from_mongo(await db.bible_hymnals.find_one({"name": _ci(name)}))
    if existing:
        return existing.model_dump()
    h = Hymnal(name=name)
    h.id = str((await db.bible_hymnals.insert_one(h.to_mongo())).inserted_id)
    return h.model_dump()


@router.put("/hymnals/last")
async def set_last_hymnal(body: LastHymnalIn):
    await db.bible_settings.update_one({"_id": "settings"}, {"$set": {"last_hymnal": body.name.strip()}}, upsert=True)
    return {"last_used": body.name.strip()}


@router.delete("/hymnals/{hymnal_id}")
async def delete_hymnal(hymnal_id: str):
    h = Hymnal.from_mongo(await db.bible_hymnals.find_one({"_id": _oid(hymnal_id)}))
    if not h:
        raise HTTPException(404, "Hymnal not found")
    await db.bible_hymnals.delete_one({"_id": _oid(hymnal_id)})
    await db.bible_settings.update_one({"_id": "settings", "last_hymnal": h.name}, {"$set": {"last_hymnal": ""}})
    return {"deleted": hymnal_id}

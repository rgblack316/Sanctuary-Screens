import re
from typing import List, Literal, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from bible_routes import available_books, default_translation
from books import display_name, resolve_query_book
from core import BIBLE_AUTH, db, now_iso
from models import BaseDocument
from reference import RefError, format_reference, parse_reference

router = APIRouter(prefix="/bible", dependencies=[BIBLE_AUTH])


class LibraryItem(BaseDocument):
    name: str
    kind: str = "scripture"
    reference: str
    translation_code: Optional[str] = None
    preloaded_text_optional: str = ""
    reference_only: bool = False
    created_at: str


Kind = Literal["scripture", "hymn", "custom"]


class LibraryIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    kind: Kind = "scripture"
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


def _kind_filter(kind: Optional[str]) -> dict:
    if kind == "scripture":  # older rows may have no kind at all
        return {"$or": [{"kind": "scripture"}, {"kind": {"$exists": False}}]}
    return {"kind": kind}


@router.get("/library")
async def list_library(q: str = Query("", max_length=200), kind: Optional[Kind] = None,
                       limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    """Library slides, optionally filtered by kind and a text search (name, reference or slide text)."""
    conds = []
    if kind:
        conds.append(_kind_filter(kind))
    if q.strip():
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        conds.append({"$or": [{"name": rx}, {"reference": rx}, {"preloaded_text_optional": rx}]})
    flt = {"$and": conds} if conds else {}
    total = await db.bible_library.count_documents(flt)
    docs = await db.bible_library.find(flt).sort("name", 1).skip(offset).limit(limit).to_list(limit)
    counts = {k: await db.bible_library.count_documents(_kind_filter(k)) for k in ("scripture", "hymn", "custom")}
    return {"items": [LibraryItem.from_mongo(d).model_dump() for d in docs], "total": total,
            "limit": limit, "offset": offset, "counts": counts}


async def _normalized_scripture(text: str, code: Optional[str]) -> Optional[str]:
    """'jn 3:16' -> 'John 3:16' using the same parser as lookup, or None if it is not a reference."""
    try:
        book_raw, spans = parse_reference(text)
    except RefError:
        return None
    for c in dict.fromkeys([code, await default_translation()]):  # the chosen translation, else the default one
        if not c:
            continue
        books = await available_books(c)
        norm = resolve_query_book(book_raw, books)
        if norm:
            return format_reference(display_name(books[norm]), spans)
    return None


@router.get("/library/match")
async def match_library(text: str = Query("", max_length=200), kind: Optional[Kind] = None,
                        translation_code: Optional[str] = None, limit: int = Query(6, ge=1, le=20)):
    """Slides already in the library that match what is being typed, so nothing is built twice.

    `exact` marks a slide that is the same thing (same reference/title, and same translation when given).
    """
    t = text.strip()
    if len(t) < 2:
        return {"normalized": None, "items": []}
    normalized = await _normalized_scripture(t, translation_code) if kind in (None, "scripture") else None
    rx = {"$regex": re.escape(t), "$options": "i"}
    ors = [{"name": rx}, {"reference": rx}]
    if normalized:
        ors.append({"reference": {"$regex": f"^{re.escape(normalized)}$", "$options": "i"}})
    conds = [{"$or": ors}]
    if kind:
        conds.append(_kind_filter(kind))
    docs = await db.bible_library.find({"$and": conds}).sort("name", 1).to_list(200)
    wanted = (normalized or t).lower()
    out = []
    for d in docs:
        item = LibraryItem.from_mongo(d).model_dump()
        same_ref = item["reference"].strip().lower() == wanted or item["name"].strip().lower() == t.lower()
        same_tr = (not translation_code) or item["kind"] != "scripture" or item.get("translation_code") in (None, translation_code)
        item["exact"] = bool(same_ref and same_tr)
        out.append(item)
    out.sort(key=lambda i: (not i["exact"], i["name"].lower()))
    return {"normalized": normalized, "items": out[:limit]}


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

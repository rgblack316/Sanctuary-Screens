from pathlib import Path
from typing import List, Literal, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from appearance import get_appearance, get_site
from books import display_name, resolve_query_book
from core import (BIBLE_AUTH, IDLE_DIR, IDLE_SUBTITLE, IDLE_TITLE, MAX_SLIDES, db, hub, now_iso)
from importer import validate_csv
from models import Passage, PreparedItem, Translation, VerseSlide
from reference import RefError, format_reference, format_span, parse_reference

router = APIRouter(prefix="/bible")
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
_books_cache: dict = {}


# ---------- helpers ----------

def idle_image() -> Optional[Path]:
    if not IDLE_DIR.is_dir():
        return None
    files = sorted(p for p in IDLE_DIR.iterdir() if p.suffix.lower() in IMAGE_EXT)
    return files[0] if files else None


def idle_config() -> dict:
    img = idle_image()
    url = f"/api/bible/idle-image?v={int(img.stat().st_mtime)}" if img else None
    return {"title": IDLE_TITLE, "subtitle": IDLE_SUBTITLE, "image_url": url}


async def available_books(code: str) -> dict:
    if code not in _books_cache:
        rows = await db.bible_verses.aggregate([
            {"$match": {"translation_code": code}},
            {"$group": {"_id": "$book_normalized", "name": {"$first": "$book_name"}}},
        ]).to_list(None)
        _books_cache[code] = {r["_id"]: r["name"] for r in rows}
    return _books_cache[code]


async def get_translation(code: str) -> Translation:
    t = Translation.from_mongo(await db.bible_translations.find_one({"translation_code": code, "import_status": "ready"}))
    if not t:
        raise HTTPException(404, f"Translation '{code}' is not installed.")
    return t


async def lookup_passage(reference: str, code: str) -> dict:
    t = await get_translation(code)
    try:
        book_raw, spans = parse_reference(reference)
    except RefError as e:
        raise HTTPException(422, str(e))
    books = await available_books(code)
    norm = resolve_query_book(book_raw, books)
    if not norm:
        raise HTTPException(404, f"Book '{book_raw}' was not found in {code}. Check spelling or enter the text manually.")
    disp = display_name(books[norm])
    slides, warnings = [], []
    for sc, sv, ec, ev in spans:
        lo, hi = (sc, sv or 1), (ec, ev if ev is not None else 10**6)
        cursor = db.bible_verses.find(
            {"translation_code": code, "book_normalized": norm, "chapter": {"$gte": sc, "$lte": ec}},
            {"_id": 0, "chapter": 1, "verse": 1, "text": 1, "book_name": 1},
        ).sort([("chapter", 1), ("verse", 1)])
        found = [d async for d in cursor if lo <= (d["chapter"], d["verse"]) <= hi]
        label = f"{disp} {format_span(sc, sv, ec, ev)}"
        if not found:
            warnings.append(f"No verses found for {label} in {code}.")
        elif sv is not None and ((found[0]["chapter"], found[0]["verse"]) != lo or
                                 (found[-1]["chapter"], found[-1]["verse"]) != hi):
            warnings.append(f"Some verses in {label} are missing from {code}.")
        slides.extend(VerseSlide(reference_label=f"{disp} {d['chapter']}:{d['verse']}", verse_text=d["text"],
                                 book_name=d["book_name"], chapter=d["chapter"], verse=d["verse"]) for d in found)
        if len(slides) > MAX_SLIDES:
            raise HTTPException(422, f"That passage has more than {MAX_SLIDES} verses. Choose a smaller range.")
    normalized = format_reference(disp, spans)
    if not slides:
        raise HTTPException(404, f"No verses found for {normalized} in {code}. You can enter the text manually.")
    return {"reference_input": reference, "normalized_reference": normalized, "translation_code": code,
            "translation_name": t.translation_name, "source_type": "local_lookup",
            "verses": [s.model_dump() for s in slides], "warnings": warnings}


async def display_doc() -> dict:
    return await db.bible_display.find_one({"_id": "state"}) or {}


async def active_passage() -> Optional[Passage]:
    st = await display_doc()
    if st.get("mode") != "passage" or not st.get("active_passage_id"):
        return None
    return Passage.from_mongo(await db.bible_passages.find_one({"_id": ObjectId(st["active_passage_id"])}))


async def bible_state() -> dict:
    st = await display_doc()
    base = {"mode": "idle", "idle": idle_config(), "updated_at": st.get("updated_at"),
            "appearance": await get_appearance("bible"), **(await get_site())}
    p = await active_passage()
    if not p or not p.verses:
        return base
    idx = max(0, min(st.get("active_slide_index", 0), len(p.verses) - 1))
    t = Translation.from_mongo(await db.bible_translations.find_one({"translation_code": p.translation_code})) \
        if p.translation_code else None
    return {**base, "mode": "passage", "passage_id": p.id, "reference": p.normalized_reference,
            "translation_code": p.translation_code, "translation_name": t.translation_name if t else None,
            "source_type": p.source_type, "slide_index": idx, "total": len(p.verses),
            "slide": p.verses[idx].model_dump(), "slides": [v.model_dump() for v in p.verses]}


async def set_display(mode: str, passage_id: Optional[str] = None, index: int = 0) -> dict:
    await db.bible_display.update_one({"_id": "state"}, {"$set": {
        "mode": mode, "active_passage_id": passage_id, "active_slide_index": index, "updated_at": now_iso()}},
        upsert=True)
    if passage_id:
        await db.bible_passages.update_one({"_id": ObjectId(passage_id)},
                                           {"$set": {"active_slide_index": index, "updated_at": now_iso()}})
    state = await bible_state()
    await hub.broadcast("bible", state)
    return state


async def default_translation() -> Optional[str]:
    s = await db.bible_settings.find_one({"_id": "settings"}) or {}
    code = s.get("default_translation")
    if code and await db.bible_translations.find_one({"translation_code": code, "import_status": "ready"}):
        return code
    first = await db.bible_translations.find_one({"import_status": "ready"}, sort=[("created_at", 1)])
    return first["translation_code"] if first else None


async def commit_import(rows, report, name: str, filename: str, replace: bool) -> Translation:
    code = report["translation_code"]
    existing = Translation.from_mongo(await db.bible_translations.find_one({"translation_code": code}))
    if existing and existing.import_status == "ready" and not replace:
        raise HTTPException(409, f"{code} is already installed. Tick 'Replace existing' to re-import it.")
    staging = f"__staging__{code}"
    await db.bible_verses.delete_many({"translation_code": staging})
    for r in rows:
        r["translation_code"] = staging
    try:
        for i in range(0, len(rows), 5000):
            await db.bible_verses.insert_many(rows[i:i + 5000], ordered=False)
    except Exception as e:
        await db.bible_verses.delete_many({"translation_code": staging})
        raise HTTPException(500, f"Import failed while writing verses: {e}")
    await db.bible_verses.delete_many({"translation_code": code})
    await db.bible_verses.update_many({"translation_code": staging}, {"$set": {"translation_code": code}})
    _books_cache.pop(code, None)
    ts = now_iso()
    t = Translation(translation_code=code, translation_name=(name or "").strip() or (existing.translation_name if existing else code),
                    source_filename=filename, import_status="ready", verse_count=report["row_count"],
                    book_count=report["book_count"], import_version=(existing.import_version + 1) if existing else 1,
                    created_at=existing.created_at if existing else ts, updated_at=ts)
    await db.bible_translations.update_one({"translation_code": code},
                                           {"$set": {**t.to_mongo(), "last_import_report": report}}, upsert=True)
    return t


def oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise HTTPException(404, "Not found")


# ---------- public display ----------

@router.get("/display")
async def get_display():
    return await bible_state()


@router.get("/idle-image")
async def get_idle_image():
    img = idle_image()
    if not img:
        raise HTTPException(404, "No idle image configured")
    return FileResponse(img)


# ---------- translations ----------

@router.get("/translations", dependencies=[BIBLE_AUTH])
async def list_translations():
    docs = await db.bible_translations.find({"import_status": "ready"}).sort("created_at", 1).to_list(None)
    p = await active_passage()
    default = await default_translation()
    items = []
    for d in docs:
        t = Translation.from_mongo(d)
        items.append({**t.model_dump(), "is_default": t.translation_code == default,
                      "is_live": bool(p and p.translation_code == t.translation_code)})
    return {"translations": items, "default_translation": default}


@router.post("/translations/validate", dependencies=[BIBLE_AUTH])
async def validate_translation(file: UploadFile = File(...)):
    report, _ = validate_csv(await file.read())
    if report["translation_code"]:
        report["already_installed"] = bool(await db.bible_translations.find_one(
            {"translation_code": report["translation_code"], "import_status": "ready"}))
    return report


@router.post("/translations/import", dependencies=[BIBLE_AUTH])
async def import_translation(file: UploadFile = File(...), translation_name: str = Form(""),
                             replace: bool = Form(False)):
    report, rows = validate_csv(await file.read())
    if not report["ok"]:
        return {"ok": False, "report": report}
    t = await commit_import(rows, report, translation_name, file.filename or "", replace)
    if not (await db.bible_settings.find_one({"_id": "settings"}) or {}).get("default_translation"):
        await db.bible_settings.update_one({"_id": "settings"}, {"$set": {"default_translation": t.translation_code}}, upsert=True)
    return {"ok": True, "report": report, "translation": t.model_dump()}


@router.delete("/translations/{code}", dependencies=[BIBLE_AUTH])
async def delete_translation(code: str, confirm: bool = False):
    await get_translation(code)
    if not confirm:
        raise HTTPException(400, "Deletion must be confirmed.")
    p = await active_passage()
    if p and p.translation_code == code:
        raise HTTPException(409, f"{code} is on the live display. Clear the display or switch translation first.")
    if await db.bible_translations.count_documents({"import_status": "ready"}) <= 1:
        raise HTTPException(409, "This is the last installed translation. Import a replacement before deleting it.")
    res = await db.bible_verses.delete_many({"translation_code": code})
    await db.bible_translations.delete_one({"translation_code": code})
    _books_cache.pop(code, None)
    s = await db.bible_settings.find_one({"_id": "settings"}) or {}
    if s.get("default_translation") == code:
        await db.bible_settings.update_one({"_id": "settings"}, {"$set": {"default_translation": None}})
    return {"deleted": code, "verses_removed": res.deleted_count, "default_translation": await default_translation()}


class SettingsIn(BaseModel):
    default_translation: str


@router.put("/settings", dependencies=[BIBLE_AUTH])
async def update_settings(body: SettingsIn):
    await get_translation(body.default_translation)
    await db.bible_settings.update_one({"_id": "settings"}, {"$set": {"default_translation": body.default_translation}},
                                       upsert=True)
    return {"default_translation": body.default_translation}


# ---------- lookup & live control ----------

class LookupIn(BaseModel):
    reference: str = Field(..., min_length=1, max_length=200)
    translation_code: str


@router.post("/lookup", dependencies=[BIBLE_AUTH])
async def lookup(body: LookupIn):
    return await lookup_passage(body.reference, body.translation_code)


class SlideIn(BaseModel):
    reference_label: str = Field(..., min_length=1, max_length=120)
    verse_text: str = Field(..., min_length=1, max_length=5000)
    book_name: str = ""
    chapter: Optional[int] = None
    verse: Optional[int] = None


class PublishIn(BaseModel):
    reference_input: str = Field("", max_length=200)
    normalized_reference: str = Field(..., min_length=1, max_length=200)
    translation_code: Optional[str] = None
    source_type: Literal["local_lookup", "manual"]
    verses: List[SlideIn] = Field(..., min_length=1, max_length=MAX_SLIDES)
    start_index: int = 0


@router.post("/publish", dependencies=[BIBLE_AUTH])
async def publish(body: PublishIn):
    if body.translation_code:
        await get_translation(body.translation_code)
    idx = max(0, min(body.start_index, len(body.verses) - 1))
    p = Passage(reference_input=body.reference_input, normalized_reference=body.normalized_reference.strip(),
                translation_code=body.translation_code, source_type=body.source_type,
                verses=[VerseSlide(**v.model_dump()) for v in body.verses], active_slide_index=idx,
                status="live", updated_at=now_iso())
    await db.bible_passages.update_many({"status": "live"}, {"$set": {"status": "ended"}})
    res = await db.bible_passages.insert_one(p.to_mongo())
    return await set_display("passage", str(res.inserted_id), idx)


class GotoIn(BaseModel):
    index: int


async def _move(delta: Optional[int] = None, index: Optional[int] = None) -> dict:
    st = await display_doc()
    p = await active_passage()
    if not p:
        raise HTTPException(409, "No scripture is on the display.")
    cur = st.get("active_slide_index", 0)
    new = index if index is not None else cur + delta
    return await set_display("passage", p.id, max(0, min(new, len(p.verses) - 1)))


@router.post("/display/next", dependencies=[BIBLE_AUTH])
async def next_slide():
    return await _move(delta=1)


@router.post("/display/prev", dependencies=[BIBLE_AUTH])
async def prev_slide():
    return await _move(delta=-1)


@router.post("/display/goto", dependencies=[BIBLE_AUTH])
async def goto_slide(body: GotoIn):
    return await _move(index=body.index)


@router.post("/display/clear", dependencies=[BIBLE_AUTH])
async def clear_display():
    await db.bible_passages.update_many({"status": "live"}, {"$set": {"status": "ended"}})
    return await set_display("idle")


class SwitchIn(BaseModel):
    translation_code: str


@router.post("/display/translation", dependencies=[BIBLE_AUTH])
async def switch_translation(body: SwitchIn):
    p = await active_passage()
    if not p:
        raise HTTPException(409, "No scripture is on the display.")
    if p.source_type != "local_lookup":
        raise HTTPException(409, "Manual text cannot be switched to another translation.")
    result = await lookup_passage(p.normalized_reference, body.translation_code)
    st = await display_doc()
    idx = max(0, min(st.get("active_slide_index", 0), len(result["verses"]) - 1))
    await db.bible_passages.update_one({"_id": ObjectId(p.id)}, {"$set": {
        "translation_code": body.translation_code, "verses": result["verses"], "updated_at": now_iso()}})
    return await set_display("passage", p.id, idx)


# ---------- prepared list ----------

class PreparedIn(BaseModel):
    service_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    title_or_note: str = Field("", max_length=120)
    reference: str = Field(..., min_length=1, max_length=200)
    translation_code: Optional[str] = None
    preloaded_text_optional: str = Field("", max_length=20000)


class MoveIn(BaseModel):
    direction: Literal["up", "down"]


@router.get("/prepared", dependencies=[BIBLE_AUTH])
async def list_prepared(service_date: str):
    docs = await db.bible_prepared.find({"service_date": service_date}).sort("sort_order", 1).to_list(None)
    return {"items": [PreparedItem.from_mongo(d).model_dump() for d in docs]}


@router.post("/prepared", dependencies=[BIBLE_AUTH])
async def create_prepared(body: PreparedIn):
    last = await db.bible_prepared.find_one({"service_date": body.service_date}, sort=[("sort_order", -1)])
    item = PreparedItem(**body.model_dump(), sort_order=(last["sort_order"] + 1) if last else 0)
    res = await db.bible_prepared.insert_one(item.to_mongo())
    item.id = str(res.inserted_id)
    return item.model_dump()


@router.put("/prepared/{item_id}", dependencies=[BIBLE_AUTH])
async def update_prepared(item_id: str, body: PreparedIn):
    res = await db.bible_prepared.update_one({"_id": oid(item_id)}, {"$set": body.model_dump()})
    if not res.matched_count:
        raise HTTPException(404, "Prepared item not found")
    return PreparedItem.from_mongo(await db.bible_prepared.find_one({"_id": oid(item_id)})).model_dump()


@router.delete("/prepared/{item_id}", dependencies=[BIBLE_AUTH])
async def delete_prepared(item_id: str):
    res = await db.bible_prepared.delete_one({"_id": oid(item_id)})
    if not res.deleted_count:
        raise HTTPException(404, "Prepared item not found")
    return {"deleted": item_id}


@router.post("/prepared/{item_id}/move", dependencies=[BIBLE_AUTH])
async def move_prepared(item_id: str, body: MoveIn):
    item = PreparedItem.from_mongo(await db.bible_prepared.find_one({"_id": oid(item_id)}))
    if not item:
        raise HTTPException(404, "Prepared item not found")
    up = body.direction == "up"
    other = await db.bible_prepared.find_one(
        {"service_date": item.service_date, "sort_order": {"$lt" if up else "$gt": item.sort_order}},
        sort=[("sort_order", -1 if up else 1)])
    if other:
        await db.bible_prepared.update_one({"_id": oid(item.id)}, {"$set": {"sort_order": other["sort_order"]}})
        await db.bible_prepared.update_one({"_id": other["_id"]}, {"$set": {"sort_order": item.sort_order}})
    return await list_prepared(item.service_date)

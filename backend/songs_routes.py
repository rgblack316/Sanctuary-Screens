"""Hymnal / songbook index: import a CSV of songbook, title and page number, then look songs up by page,
song number or title so a hymn slide can be built in a couple of clicks."""
import csv
import io
import re
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse

from core import BIBLE_AUTH, db, now_iso

router = APIRouter(prefix="/bible/songs", dependencies=[BIBLE_AUTH])

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_ROWS = 50_000
MAX_ERRORS = 50
ALIASES = {
    "songbook": {"songbook", "song book", "song_book", "hymnal", "hymn book", "hymnbook", "book"},
    "title": {"title", "song title", "song", "hymn", "hymn title", "name"},
    "page": {"page", "page number", "page_number", "page no", "page #", "pg"},
    "number": {"number", "song number", "song_number", "hymn number", "no", "#"},
}
SAMPLE_CSV = "songbook,title,page,number\nBaptist Hymnal,Amazing Grace,112,45\nBaptist Hymnal,Blessed Assurance,112,46\n"


def key(value: str) -> str:
    """Comparison key: lower-case, single spaces, and '012' == '12' for numbers and pages."""
    v = re.sub(r"\s+", " ", (value or "").strip()).lower()
    return str(int(v)) if v.isdigit() else v


def _headers(fieldnames):
    mapped = {}
    for raw in fieldnames or []:
        h = re.sub(r"\s+", " ", (raw or "").strip().lower())
        for canon, names in ALIASES.items():
            if h in names and canon not in mapped.values():
                mapped[raw] = canon
    return mapped


def validate_songs_csv(raw: bytes):
    errors, total = [], 0

    def err(row, msg):
        nonlocal total
        total += 1
        if len(errors) < MAX_ERRORS:
            errors.append({"row": row, "error": msg})

    report = {"ok": False, "row_count": 0, "duplicates": 0, "songbooks": {}, "columns": [], "errors": errors,
              "error_count": 0}
    if len(raw) > MAX_FILE_BYTES:
        err(0, "File is larger than 10 MB.")
        report["error_count"] = total
        return report, []
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        err(0, "File is not UTF-8 encoded text.")
        report["error_count"] = total
        return report, []
    first = text.split("\n", 1)[0]
    delim = max([",", ";", "\t"], key=first.count)
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    cols = _headers(reader.fieldnames)
    report["columns"] = [c for c in (reader.fieldnames or [])]
    missing = [c for c in ("songbook", "title", "page") if c not in cols.values()]
    if missing:
        err(1, f"Missing required column(s): {', '.join(missing)}. Expected: songbook, title, page (optional: number).")
        report["error_count"] = total
        return report, []

    rows, seen = [], set()
    for line, r in enumerate(reader, start=2):
        if None in r:
            err(line, "Row has more fields than the header.")
            continue
        v = {cols[k]: (val or "").strip() for k, val in r.items() if k in cols}
        if not any(v.values()):
            continue
        problems = []
        if not v.get("songbook"):
            problems.append("songbook is empty")
        elif len(v["songbook"]) > 80:
            problems.append("songbook is longer than 80 characters")
        if not v.get("title"):
            problems.append("title is empty")
        elif len(v["title"]) > 160:
            problems.append("title is longer than 160 characters")
        if not v.get("page"):
            problems.append("page is empty")
        elif len(v["page"]) > 12:
            problems.append("page is longer than 12 characters")
        if len(v.get("number", "")) > 12:
            problems.append("number is longer than 12 characters")
        if problems:
            err(line, "; ".join(problems))
            continue
        ident = (key(v["songbook"]), key(v["title"]), key(v["page"]))
        if ident in seen:
            report["duplicates"] += 1
            continue
        seen.add(ident)
        if len(rows) >= MAX_ROWS:
            err(line, f"More than {MAX_ROWS:,} songs in one file.")
            break
        rows.append({"songbook": v["songbook"], "songbook_key": ident[0], "title": v["title"], "title_key": ident[1],
                     "page": v["page"], "page_key": ident[2], "number": v.get("number", ""),
                     "number_key": key(v.get("number", ""))})
    if not rows and total == 0:
        err(0, "File contains no songs.")
    names = {}
    for r in rows:
        names[r["songbook"]] = names.get(r["songbook"], 0) + 1
    report.update(ok=total == 0, row_count=len(rows), songbooks=names, error_count=total)
    return report, rows


def _public(d: dict) -> dict:
    return {"id": str(d["_id"]), "songbook": d["songbook"], "title": d["title"], "page": d["page"],
            "number": d.get("number", "")}


async def _canonical_names(rows: list) -> None:
    """Reuse the spelling of a songbook that already exists, whatever its letter case."""
    known = {key(h["name"]): h["name"] async for h in db.bible_hymnals.find()}
    async for g in db.hymnal_songs.aggregate([{"$group": {"_id": "$songbook_key", "name": {"$first": "$songbook"}}}]):
        known[g["_id"]] = g["name"]
    for r in rows:
        r["songbook"] = known.get(r["songbook_key"], r["songbook"])


@router.get("/sample.csv")
async def sample_csv():
    return PlainTextResponse(SAMPLE_CSV, media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="songbook-sample.csv"'})


@router.post("/validate")
async def validate(file: UploadFile = File(...)):
    report, rows = validate_songs_csv(await file.read(MAX_FILE_BYTES + 1))
    existing = {}
    for name in report["songbooks"]:
        existing[name] = await db.hymnal_songs.count_documents({"songbook_key": key(name)})
    report["existing"] = existing
    return report


@router.post("/import")
async def import_songs(file: UploadFile = File(...), replace: bool = Form(True)):
    report, rows = validate_songs_csv(await file.read(MAX_FILE_BYTES + 1))
    if not report["ok"]:
        return {"ok": False, "report": report}
    await _canonical_names(rows)
    keys = {r["songbook_key"] for r in rows}
    if replace:
        await db.hymnal_songs.delete_many({"songbook_key": {"$in": list(keys)}})
    else:
        have = {(d["songbook_key"], d["title_key"], d["page_key"]) async for d in
                db.hymnal_songs.find({"songbook_key": {"$in": list(keys)}}, {"songbook_key": 1, "title_key": 1, "page_key": 1})}
        rows = [r for r in rows if (r["songbook_key"], r["title_key"], r["page_key"]) not in have]
    ts = now_iso()
    for r in rows:
        r["created_at"] = ts
    for i in range(0, len(rows), 5000):
        await db.hymnal_songs.insert_many(rows[i:i + 5000])
    for name in {r["songbook"] for r in rows}:
        if not await db.bible_hymnals.find_one({"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}):
            await db.bible_hymnals.insert_one({"name": name})
    return {"ok": True, "imported": len(rows), "songbooks": report["songbooks"], "report": report}


@router.get("/books")
async def books():
    rows = await db.hymnal_songs.aggregate([
        {"$group": {"_id": "$songbook_key", "name": {"$first": "$songbook"}, "count": {"$sum": 1}}},
        {"$sort": {"name": 1}}]).to_list(None)
    return {"songbooks": [{"name": r["name"], "count": r["count"]} for r in rows]}


@router.delete("/books/{name}")
async def delete_book(name: str, confirm: bool = False):
    if not confirm:
        raise HTTPException(400, "Deletion must be confirmed.")
    res = await db.hymnal_songs.delete_many({"songbook_key": key(name)})
    if not res.deleted_count:
        raise HTTPException(404, "No songs from that songbook.")
    return {"deleted": name, "songs_removed": res.deleted_count}


def _page_sort(d: dict):
    p = d.get("page_key", "")
    return (0, int(p), d["title"].lower()) if p.isdigit() else (1, 0, f"{p} {d['title'].lower()}")


@router.get("/search")
async def search(q: str = Query("", max_length=160), songbook: Optional[str] = Query(None, max_length=80),
                 limit: int = Query(25, ge=1, le=100)):
    """Look songs up by page or song number (digits) or by part of the title.

    Several songs can share a page, so every match is returned and the person picks the right one.
    """
    text = q.strip()
    if not text:
        return {"items": [], "total": 0}
    flt: dict = {}
    if songbook:
        flt["songbook_key"] = key(songbook)
    if text.replace(" ", "").isdigit():
        k = key(text.replace(" ", ""))
        flt["$or"] = [{"page_key": k}, {"number_key": k}]
    else:
        flt["title"] = {"$regex": re.escape(text), "$options": "i"}
    docs = await db.hymnal_songs.find(flt).to_list(500)
    docs.sort(key=_page_sort)
    items = []
    for d in docs[:limit]:
        it = _public(d)
        if "$or" in flt:
            k = flt["$or"][0]["page_key"]
            it["matched_on"] = [n for n, f in (("page", d.get("page_key") == k), ("number", d.get("number_key") == k)) if f]
        items.append(it)
    return {"items": items, "total": len(docs)}

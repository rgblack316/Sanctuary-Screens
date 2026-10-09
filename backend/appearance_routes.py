from typing import Literal

from bson import Binary, ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from appearance import DEFAULTS, AppearanceIn, get_appearance, get_site
from bible_routes import bible_state
from core import SETTINGS_AUTH, db, hub, now_iso
from register_routes import register_state

router = APIRouter(prefix="/appearance")
Display = Literal["register", "bible"]
MAX_IMAGE = 12 * 1024 * 1024
IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}


async def _broadcast(display: str):
    await hub.broadcast(display, await (register_state() if display == "register" else bible_state()))


async def _broadcast_all():
    await _broadcast("register")
    await _broadcast("bible")


async def _store_image(file: UploadFile, tag: str) -> str:
    if file.content_type not in IMAGE_TYPES:
        raise HTTPException(415, "Use a PNG, JPG, WEBP or GIF image.")
    data = await file.read()
    if not data:
        raise HTTPException(422, "The image file is empty.")
    if len(data) > MAX_IMAGE:
        raise HTTPException(413, "Image is larger than 12 MB. Please use a smaller image.")
    res = await db.display_images.insert_one({"display": tag, "filename": file.filename or "",
                                              "content_type": file.content_type, "size": len(data),
                                              "data": Binary(data), "created_at": now_iso()})
    return str(res.inserted_id)


async def _result(display: str) -> dict:
    return {"appearance": await get_appearance(display), "defaults": DEFAULTS[display], **(await get_site())}


class ChurchNameIn(BaseModel):
    church_name: str = Field("", max_length=120)


@router.put("/church-name", dependencies=[SETTINGS_AUTH])
async def update_church_name(body: ChurchNameIn):
    name = body.church_name.strip()
    await db.site_settings.update_one({"_id": "site"}, {"$set": {"church_name": name, "updated_at": now_iso()}},
                                      upsert=True)
    await _broadcast_all()
    return {"church_name": name}


@router.post("/logo", dependencies=[SETTINGS_AUTH])
async def upload_logo(file: UploadFile = File(...)):
    new_id = await _store_image(file, "logo")
    old = (await db.site_settings.find_one({"_id": "site"}) or {}).get("logo_image_id")
    await db.site_settings.update_one({"_id": "site"}, {"$set": {"logo_image_id": new_id, "updated_at": now_iso()}},
                                      upsert=True)
    if old:
        await db.display_images.delete_one({"_id": ObjectId(old)})
    await _broadcast_all()
    return await get_site()


@router.delete("/logo", dependencies=[SETTINGS_AUTH])
async def delete_logo():
    old = (await db.site_settings.find_one({"_id": "site"}) or {}).get("logo_image_id")
    if old:
        await db.display_images.delete_one({"_id": ObjectId(old)})
        await db.site_settings.update_one({"_id": "site"}, {"$set": {"logo_image_id": None, "updated_at": now_iso()}})
        await _broadcast_all()
    return await get_site()


@router.get("/image/{image_id}")
async def get_image(image_id: str):
    try:
        doc = await db.display_images.find_one({"_id": ObjectId(image_id)})
    except InvalidId:
        doc = None
    if not doc:
        raise HTTPException(404, "Image not found")
    return Response(content=bytes(doc["data"]), media_type=doc["content_type"],
                    headers={"Cache-Control": "public, max-age=31536000, immutable"})


@router.get("/{display}", dependencies=[SETTINGS_AUTH])
async def read_appearance(display: Display):
    return await _result(display)


@router.put("/{display}", dependencies=[SETTINGS_AUTH])
async def update_appearance(display: Display, body: AppearanceIn):
    await db.display_appearance.update_one({"_id": display}, {"$set": {**body.model_dump(), "updated_at": now_iso()}},
                                           upsert=True)
    await _broadcast(display)
    return await _result(display)


@router.post("/{display}/image", dependencies=[SETTINGS_AUTH])
async def upload_image(display: Display, file: UploadFile = File(...)):
    new_id = await _store_image(file, display)
    old = (await db.display_appearance.find_one({"_id": display}) or {}).get("image_id")
    await db.display_appearance.update_one({"_id": display}, {"$set": {"image_id": new_id,
                                                                       "updated_at": now_iso()}}, upsert=True)
    if old:
        await db.display_images.delete_one({"_id": ObjectId(old)})
    await _broadcast(display)
    return await _result(display)


@router.delete("/{display}/image", dependencies=[SETTINGS_AUTH])
async def delete_image(display: Display):
    old = (await db.display_appearance.find_one({"_id": display}) or {}).get("image_id")
    if old:
        await db.display_images.delete_one({"_id": ObjectId(old)})
        await db.display_appearance.update_one({"_id": display}, {"$set": {"image_id": None, "updated_at": now_iso()}})
        await _broadcast(display)
    return await _result(display)

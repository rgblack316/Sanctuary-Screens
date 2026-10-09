import re
from typing import Literal, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from appearance import AppearanceIn, release_image
from appearance_routes import _broadcast, _result
from core import SETTINGS_AUTH, db, now_iso
from models import BaseDocument

router = APIRouter(prefix="/appearance")
Display = Literal["register", "bible"]


class Look(BaseDocument):
    display: str
    name: str
    settings: AppearanceIn
    image_id: Optional[str] = None
    created_at: str
    updated_at: str


class LookIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    settings: AppearanceIn


def _oid(look_id: str) -> ObjectId:
    try:
        return ObjectId(look_id)
    except (InvalidId, TypeError):
        raise HTTPException(404, "Look not found")


def _out(look: Look) -> dict:
    data = look.model_dump(exclude={"image_id"})
    data["image_url"] = f"/api/appearance/image/{look.image_id}" if look.image_id else None
    return data


async def _get(display: str, look_id: str) -> Look:
    look = Look.from_mongo(await db.display_looks.find_one({"_id": _oid(look_id), "display": display}))
    if not look:
        raise HTTPException(404, "Look not found")
    return look


async def _current_image(display: str):
    return (await db.display_appearance.find_one({"_id": display}) or {}).get("image_id")


async def _name_taken(display: str, name: str, exclude: Optional[str] = None) -> bool:
    q = {"display": display, "name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}
    if exclude:
        q["_id"] = {"$ne": _oid(exclude)}
    return bool(await db.display_looks.find_one(q))


@router.get("/{display}/looks", dependencies=[SETTINGS_AUTH])
async def list_looks(display: Display):
    docs = await db.display_looks.find({"display": display}).sort("name", 1).to_list(None)
    active = (await db.display_appearance.find_one({"_id": display}) or {}).get("active_look_id")
    return {"looks": [_out(Look.from_mongo(d)) for d in docs], "active_look_id": active}


@router.post("/{display}/looks", dependencies=[SETTINGS_AUTH])
async def create_look(display: Display, body: LookIn):
    name = body.name.strip()
    if await _name_taken(display, name):
        raise HTTPException(409, f"A look named '{name}' already exists. Use Update on it instead.")
    ts = now_iso()
    look = Look(display=display, name=name, settings=body.settings, image_id=await _current_image(display),
                created_at=ts, updated_at=ts)
    res = await db.display_looks.insert_one(look.to_mongo())
    look.id = str(res.inserted_id)
    return _out(look)


@router.put("/{display}/looks/{look_id}", dependencies=[SETTINGS_AUTH])
async def update_look(display: Display, look_id: str, body: LookIn):
    look = await _get(display, look_id)
    name = body.name.strip()
    if await _name_taken(display, name, exclude=look_id):
        raise HTTPException(409, f"A look named '{name}' already exists.")
    old_image = look.image_id
    await db.display_looks.update_one({"_id": _oid(look_id)}, {"$set": {
        "name": name, "settings": body.settings.model_dump(), "image_id": await _current_image(display),
        "updated_at": now_iso()}})
    await release_image(old_image)
    return _out(await _get(display, look_id))


@router.post("/{display}/looks/{look_id}/apply", dependencies=[SETTINGS_AUTH])
async def apply_look(display: Display, look_id: str):
    look = await _get(display, look_id)
    old_image = await _current_image(display)
    await db.display_appearance.update_one({"_id": display}, {"$set": {
        **look.settings.model_dump(), "image_id": look.image_id, "active_look_id": look.id,
        "updated_at": now_iso()}}, upsert=True)
    if old_image != look.image_id:
        await release_image(old_image)
    await _broadcast(display)
    return {**(await _result(display)), "active_look_id": look.id}


@router.delete("/{display}/looks/{look_id}", dependencies=[SETTINGS_AUTH])
async def delete_look(display: Display, look_id: str):
    look = await _get(display, look_id)
    await db.display_looks.delete_one({"_id": _oid(look_id)})
    await db.display_appearance.update_one({"_id": display, "active_look_id": look_id}, {"$set": {"active_look_id": None}})
    await release_image(look.image_id)
    return {"deleted": look_id}

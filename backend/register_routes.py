from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from appearance import get_appearance, get_site
from core import CURRENCY, REGISTER_AUTH, db, hub, now_iso
from models import Service

router = APIRouter(prefix="/register")


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(422, f"Invalid service date '{value}'. Use YYYY-MM-DD.")


class ServiceIn(BaseModel):
    service_label: str = Field("", max_length=80)
    attendance: Optional[int] = Field(None, ge=0, le=1_000_000)
    offering: Optional[float] = Field(None, ge=0, le=1_000_000_000)
    comparison_service_date: Optional[str] = None
    make_active: bool = True


class ActiveIn(BaseModel):
    service_date: str


async def register_state() -> dict:
    meta = await db.register_state.find_one({"_id": "state"}) or {}
    cur = None
    if meta.get("active_service_date"):
        cur = await db.register_services.find_one({"service_date": meta["active_service_date"]})
    if not cur:
        cur = await db.register_services.find_one(sort=[("service_date", -1)])
    appearance = await get_appearance("register")
    site = await get_site()
    if not cur:
        return {"currency": CURRENCY, "current": None, "previous": None, "comparison_service_date": None,
                "appearance": appearance, **site}
    current = Service.from_mongo(cur)
    comp = current.comparison_service_date
    prev = Service.from_mongo(await db.register_services.find_one({"service_date": comp}))
    return {"currency": CURRENCY, "current": current.model_dump(),
            "previous": prev.model_dump() if prev else None, "comparison_service_date": comp,
            "comparison_overridden": current.comparison_overridden,
            "appearance": appearance, **site}


@router.get("/display")
async def get_display():
    return await register_state()


@router.get("/services", dependencies=[REGISTER_AUTH])
async def list_services():
    docs = await db.register_services.find().sort("service_date", -1).to_list(30)
    meta = await db.register_state.find_one({"_id": "state"}) or {}
    return {"services": [Service.from_mongo(d).model_dump() for d in docs],
            "active_service_date": meta.get("active_service_date")}


@router.get("/dates", dependencies=[REGISTER_AUTH])
async def list_dates():
    return {"dates": sorted(await db.register_services.distinct("service_date"))}


@router.put("/services/{service_date}", dependencies=[REGISTER_AUTH])
async def upsert_service(service_date: str, body: ServiceIn):
    d = parse_date(service_date)
    comp, overridden = (d - timedelta(days=7)).isoformat(), False
    if body.comparison_service_date:
        c = parse_date(body.comparison_service_date)
        if c >= d:
            raise HTTPException(422, "The comparison date must be before the service date.")
        if not await db.register_services.find_one({"service_date": c.isoformat()}):
            raise HTTPException(422, f"No service record exists for {c.isoformat()}.")
        comp, overridden = c.isoformat(), True
    svc = Service(service_date=d.isoformat(), service_label=body.service_label.strip(),
                  attendance=body.attendance,
                  offering=round(body.offering, 2) if body.offering is not None else None,
                  comparison_service_date=comp, comparison_overridden=overridden, updated_at=now_iso())
    await db.register_services.update_one({"service_date": svc.service_date},
                                          {"$set": svc.to_mongo()}, upsert=True)
    if body.make_active:
        await db.register_state.update_one({"_id": "state"},
                                           {"$set": {"active_service_date": svc.service_date}}, upsert=True)
    state = await register_state()
    await hub.broadcast("register", state)
    return state


@router.post("/active", dependencies=[REGISTER_AUTH])
async def set_active(body: ActiveIn):
    d = parse_date(body.service_date).isoformat()
    if not await db.register_services.find_one({"service_date": d}):
        raise HTTPException(404, f"No service record for {d}")
    await db.register_state.update_one({"_id": "state"}, {"$set": {"active_service_date": d}}, upsert=True)
    state = await register_state()
    await hub.broadcast("register", state)
    return state

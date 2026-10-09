from typing import Literal

from pydantic import BaseModel, Field

from core import db

HEX = r"^#[0-9a-fA-F]{6}$"
Position = Literal["top-left", "top-center", "top-right", "bottom-left", "bottom-center", "bottom-right"]


class AppearanceIn(BaseModel):
    background_color: str = Field("#090B10", pattern=HEX)
    text_color: str = Field("#F8FAFC", pattern=HEX)
    accent_color: str = Field("#F59E0B", pattern=HEX)
    muted_color: str = Field("#94A3B8", pattern=HEX)
    panel_color: str = Field("#121620", pattern=HEX)
    panel_opacity: int = Field(100, ge=0, le=100)
    image_blur: int = Field(0, ge=0, le=40)
    image_dim: int = Field(40, ge=0, le=95)
    image_motion: Literal["none", "parallax"] = "none"
    motion_speed: int = Field(4, ge=1, le=10)
    church_name_show: bool = True
    church_name_position: Position = "top-center"
    church_name_size: int = Field(4, ge=1, le=10)
    church_name_color: str = Field("#F8FAFC", pattern=HEX)
    church_name_uppercase: bool = True
    church_logo_show: bool = True
    church_logo_size: int = Field(5, ge=1, le=10)
    translation_show: bool = True
    translation_position: Position = "bottom-right"
    reference_size: int = Field(5, ge=1, le=10)
    verse_size: int = Field(5, ge=1, le=10)


DEFAULTS = {
    "register": AppearanceIn().model_dump(),
    "bible": AppearanceIn(panel_opacity=0).model_dump(),
}


async def get_appearance(display: str) -> dict:
    doc = await db.display_appearance.find_one({"_id": display}) or {}
    values = {k: doc[k] for k in AppearanceIn.model_fields if k in doc}
    a = AppearanceIn(**{**DEFAULTS[display], **values})
    image_id = doc.get("image_id")
    return {**a.model_dump(), "image_url": f"/api/appearance/image/{image_id}" if image_id else None}


async def get_site() -> dict:
    doc = await db.site_settings.find_one({"_id": "site"}) or {}
    logo = doc.get("logo_image_id")
    return {"church_name": doc.get("church_name", ""),
            "church_logo_url": f"/api/appearance/image/{logo}" if logo else None}

from typing import Annotated, List, Optional

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

PyObjectId = Annotated[str, BeforeValidator(lambda v: str(v) if isinstance(v, ObjectId) else v)]


class BaseDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    id: Optional[PyObjectId] = Field(default=None, alias="_id")

    @classmethod
    def from_mongo(cls, doc):
        return cls.model_validate(doc) if doc else None

    def to_mongo(self) -> dict:
        data = self.model_dump(exclude={"id"})
        if self.id:
            data["_id"] = ObjectId(self.id)
        return data


class Service(BaseDocument):
    service_date: str
    service_label: str = ""
    attendance: Optional[int] = None
    offering: Optional[float] = None
    comparison_service_date: str
    comparison_overridden: bool = False
    updated_at: str


class Translation(BaseDocument):
    translation_code: str
    translation_name: str
    source_filename: str = ""
    import_status: str
    verse_count: int = 0
    book_count: int = 0
    import_version: int = 1
    created_at: str
    updated_at: str


class VerseSlide(BaseModel):
    reference_label: str
    verse_text: str
    book_name: str = ""
    chapter: Optional[int] = None
    verse: Optional[int] = None


class Passage(BaseDocument):
    reference_input: str = ""
    normalized_reference: str
    translation_code: Optional[str] = None
    source_type: str
    verses: List[VerseSlide]
    active_slide_index: int = 0
    status: str = "live"
    updated_at: str


class PreparedItem(BaseDocument):
    service_date: str
    title_or_note: str = ""
    reference: str
    translation_code: Optional[str] = None
    preloaded_text_optional: str = ""
    sort_order: int = 0

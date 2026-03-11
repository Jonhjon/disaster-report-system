from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class EventBase(BaseModel):
    title: str
    disaster_type: str
    severity: int = Field(ge=1, le=5)
    description: str | None = None
    location_text: str
    latitude: float
    longitude: float
    occurred_at: datetime
    casualties: int = 0
    injured: int = 0
    trapped: int = 0
    status: str = "active"


class EventResponse(EventBase):
    id: UUID
    report_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EventUpdate(BaseModel):
    title: str | None = None
    severity: int | None = Field(default=None, ge=1, le=5)
    description: str | None = None
    status: str | None = None
    casualties: int | None = None
    injured: int | None = None
    trapped: int | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in {"active", "monitoring", "resolved"}:
            raise ValueError("status must be one of: active, monitoring, resolved")
        return v


class EventListResponse(BaseModel):
    items: list[EventResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class EventMapItem(BaseModel):
    id: UUID
    title: str
    disaster_type: str
    severity: int
    latitude: float
    longitude: float
    status: str
    report_count: int
    occurred_at: datetime

    model_config = {"from_attributes": True}


class EventMapResponse(BaseModel):
    items: list[EventMapItem]

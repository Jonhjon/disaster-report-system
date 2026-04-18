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
    status: str = "reported"


class EventResponse(EventBase):
    id: UUID
    report_count: int
    location_approximate: bool = False
    created_at: datetime
    updated_at: datetime
    completeness: dict = {}

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
        allowed = {"pending_clarification", "reported", "in_progress", "resolved"}
        if v is not None and v not in allowed:
            raise ValueError(
                "status must be one of: pending_clarification, reported, in_progress, resolved"
            )
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
    location_approximate: bool = False

    model_config = {"from_attributes": True}


class EventMapResponse(BaseModel):
    items: list[EventMapItem]


class EventLocationUpdate(BaseModel):
    location_text: str = Field(min_length=1, max_length=500)

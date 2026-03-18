from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class ReportResponse(BaseModel):
    id: UUID
    event_id: UUID | None
    reporter_name: str | None
    reporter_phone: str | None
    raw_message: str
    extracted_data: dict[str, Any]
    location_text: str | None
    geocoded_address: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportListResponse(BaseModel):
    items: list[ReportResponse]
    total: int

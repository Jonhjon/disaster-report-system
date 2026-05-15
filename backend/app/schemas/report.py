from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.schemas.attachment import AttachmentOut


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
    attachments: list[AttachmentOut] = []

    model_config = {"from_attributes": True}


class ReportListResponse(BaseModel):
    items: list[ReportResponse]
    total: int


def serialize_attachment(a) -> AttachmentOut:
    return AttachmentOut(
        id=a.id,
        url=f"/static/uploads/reports/{a.filename}",
        original_filename=a.original_filename,
        content_type=a.content_type,
        size_bytes=a.size_bytes,
    )


def serialize_report(r) -> ReportResponse:
    return ReportResponse(
        id=r.id,
        event_id=r.event_id,
        reporter_name=r.reporter_name,
        reporter_phone=r.reporter_phone,
        raw_message=r.raw_message,
        extracted_data=r.extracted_data,
        location_text=r.location_text,
        geocoded_address=r.geocoded_address,
        created_at=r.created_at,
        attachments=[serialize_attachment(a) for a in (r.attachments or [])],
    )

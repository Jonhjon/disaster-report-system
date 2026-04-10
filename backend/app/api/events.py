from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.disaster_report import DisasterReport
from app.schemas.event import (
    EventListResponse,
    EventLocationUpdate,
    EventMapItem,
    EventMapResponse,
    EventResponse,
    EventUpdate,
)
from app.schemas.report import ReportListResponse, ReportResponse
from app.services import event_service
from app.services.geocoding_service import geocode_address

router = APIRouter()


@router.get("/events", response_model=EventListResponse)
def list_events(
    search: str | None = None,
    disaster_type: str | None = None,
    severity_min: int | None = None,
    severity_max: int | None = None,
    status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort_by: str = "occurred_at",
    sort_order: str = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return event_service.get_events(
        db,
        search=search,
        disaster_type=disaster_type,
        severity_min=severity_min,
        severity_max=severity_max,
        status=status,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )


@router.get("/events/map", response_model=EventMapResponse)
def map_events(
    bounds: str | None = None,
    disaster_type: str | None = None,
    severity_min: int | None = None,
    status: str = "reported",
    db: Session = Depends(get_db),
):
    items = event_service.get_map_events(
        db,
        bounds=bounds,
        disaster_type=disaster_type,
        severity_min=severity_min,
        status=status,
    )
    return {"items": items}


@router.get("/events/{event_id}", response_model=EventResponse)
def get_event(event_id: UUID, db: Session = Depends(get_db)):
    event = event_service.get_event_by_id(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.put("/events/{event_id}", response_model=EventResponse)
def update_event(event_id: UUID, data: EventUpdate, db: Session = Depends(get_db)):
    event = event_service.update_event(db, event_id, data)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.patch("/events/{event_id}/location", response_model=EventMapItem)
async def update_event_location(
    event_id: UUID,
    body: EventLocationUpdate,
    db: Session = Depends(get_db),
):
    coords = await geocode_address(body.location_text)
    if not coords:
        raise HTTPException(status_code=422, detail="無法 geocode 此地址，請提供更具體的地址")
    result = event_service.update_event_location(db, event_id, body.location_text, coords)
    if not result:
        raise HTTPException(status_code=404, detail="Event not found")
    return result


@router.delete("/events/{event_id}", status_code=204)
def delete_event(event_id: UUID, db: Session = Depends(get_db)):
    deleted = event_service.delete_event(db, event_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Event not found")


@router.get("/events/{event_id}/reports", response_model=ReportListResponse)
def get_event_reports(event_id: UUID, db: Session = Depends(get_db)):
    reports = db.query(DisasterReport).filter(DisasterReport.event_id == event_id).all()
    items = [
        ReportResponse(
            id=r.id,
            event_id=r.event_id,
            reporter_name=r.reporter_name,
            reporter_phone=r.reporter_phone,
            raw_message=r.raw_message,
            extracted_data=r.extracted_data,
            location_text=r.location_text,
            geocoded_address=r.geocoded_address,
            created_at=r.created_at,
        )
        for r in reports
    ]
    return {"items": items, "total": len(items)}

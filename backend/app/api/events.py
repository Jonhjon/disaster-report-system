from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.disaster_event import DisasterEvent
from app.models.disaster_report import DisasterReport
from app.schemas.event import (
    EventListResponse,
    EventLocationUpdate,
    EventMapItem,
    EventMapResponse,
    EventResponse,
    EventUpdate,
)
from app.schemas.report import ReportListResponse, serialize_report
from app.services import event_service
from app.services.geocoding_service import geocode_address
from app.services.llm_service import merge_event_descriptions, reextract_numbers_from_description
from app.api.deps import get_current_user
from app.models.user import User

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
def update_event(event_id: UUID, data: EventUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    event = event_service.update_event(db, event_id, data)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.patch("/events/{event_id}/location", response_model=EventMapItem)
async def update_event_location(
    event_id: UUID,
    body: EventLocationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    coords = await geocode_address(body.location_text)
    if not coords:
        raise HTTPException(status_code=422, detail="無法 geocode 此地址，請提供更具體的地址")
    result = event_service.update_event_location(db, event_id, body.location_text, coords)
    if not result:
        raise HTTPException(status_code=404, detail="Event not found")
    return result


@router.delete("/events/{event_id}", status_code=204)
def delete_event(event_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    deleted = event_service.delete_event(db, event_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Event not found")


@router.post("/events/{target_event_id}/merge-from/{source_event_id}", response_model=EventResponse)
async def merge_events(
    target_event_id: UUID,
    source_event_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """將 source 事件合併進 target 事件：通報移入、描述合併、傷亡取最大值、source 刪除。"""
    if target_event_id == source_event_id:
        raise HTTPException(status_code=400, detail="來源與目標事件不可相同")

    target = db.get(DisasterEvent, target_event_id)
    if not target:
        raise HTTPException(status_code=404, detail="目標事件不存在")

    source = db.get(DisasterEvent, source_event_id)
    if not source:
        raise HTTPException(status_code=404, detail="來源事件不存在")

    # 合併描述
    merged_desc = target.description or ""
    if source.description:
        try:
            merged_desc = await merge_event_descriptions(
                target.description or "", source.description
            )
        except Exception:
            sep = "；" if target.description else ""
            merged_desc = f"{target.description or ''}{sep}{source.description}"

    target.description = merged_desc

    # 從合併後描述重新萃取傷亡數字
    try:
        extracted = await reextract_numbers_from_description(merged_desc)
    except Exception:
        extracted = {}

    if extracted:
        if "casualties" in extracted:
            target.casualties = extracted["casualties"]
        if "injured" in extracted:
            target.injured = extracted["injured"]
        if "trapped" in extracted:
            target.trapped = extracted["trapped"]
        if "severity" in extracted:
            target.severity = max(target.severity, extracted["severity"])
        else:
            target.severity = max(target.severity, source.severity)
    else:
        target.casualties = (target.casualties or 0) + (source.casualties or 0)
        target.injured = (target.injured or 0) + (source.injured or 0)
        target.trapped = (target.trapped or 0) + (source.trapped or 0)
        target.severity = max(target.severity, source.severity)

    # 通報全部移入 target
    db.query(DisasterReport).filter(
        DisasterReport.event_id == source_event_id
    ).update({"event_id": target_event_id})

    target.report_count = (target.report_count or 1) + (source.report_count or 1)
    target.updated_at = datetime.now(timezone.utc)

    db.delete(source)
    db.commit()
    result = event_service.get_event_by_id(db, target.id)
    if not result:
        raise HTTPException(status_code=404, detail="Event not found after merge")
    return result


@router.get("/events/{event_id}/reports", response_model=ReportListResponse)
def get_event_reports(event_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    reports = db.query(DisasterReport).filter(DisasterReport.event_id == event_id).all()
    items = [serialize_report(r) for r in reports]
    return {"items": items, "total": len(items)}

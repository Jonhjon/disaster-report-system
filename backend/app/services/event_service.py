import math
from datetime import datetime
from uuid import UUID

from geoalchemy2.functions import ST_X, ST_Y
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.disaster_event import DisasterEvent
from app.models.disaster_report import DisasterReport
from app.schemas.event import EventResponse, EventUpdate, EventMapItem
from geoalchemy2.functions import ST_SetSRID, ST_MakePoint


def _event_to_response(event: DisasterEvent) -> EventResponse:
    """Convert a DisasterEvent model (with lat/lng columns) to EventResponse."""
    return EventResponse(
        id=event.id,
        title=event.title,
        disaster_type=event.disaster_type,
        severity=event.severity,
        description=event.description,
        location_text=event.location_text,
        latitude=event.lat,
        longitude=event.lng,
        occurred_at=event.occurred_at,
        casualties=event.casualties,
        injured=event.injured,
        trapped=event.trapped,
        status=event.status,
        report_count=event.report_count,
        location_approximate=event.location_approximate,
        created_at=event.created_at,
        updated_at=event.updated_at,
    )


def get_events(
    db: Session,
    *,
    search: str | None = None,
    disaster_type: str | None = None,
    severity_min: int | None = None,
    severity_max: int | None = None,
    status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort_by: str = "occurred_at",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    # Query with lat/lng extracted from geometry
    query = db.query(
        DisasterEvent,
        ST_Y(DisasterEvent.location).label("lat"),
        ST_X(DisasterEvent.location).label("lng"),
    )

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                DisasterEvent.title.ilike(pattern),
                DisasterEvent.description.ilike(pattern),
                DisasterEvent.location_text.ilike(pattern),
            )
        )
    if disaster_type:
        query = query.filter(DisasterEvent.disaster_type == disaster_type)
    if severity_min is not None:
        query = query.filter(DisasterEvent.severity >= severity_min)
    if severity_max is not None:
        query = query.filter(DisasterEvent.severity <= severity_max)
    if status:
        query = query.filter(DisasterEvent.status == status)
    if date_from:
        query = query.filter(DisasterEvent.occurred_at >= date_from)
    if date_to:
        query = query.filter(DisasterEvent.occurred_at <= date_to)

    # Count total before pagination
    total = query.count()

    # Sort
    allowed_sort = {
        "occurred_at": DisasterEvent.occurred_at,
        "severity": DisasterEvent.severity,
        "report_count": DisasterEvent.report_count,
        "created_at": DisasterEvent.created_at,
    }
    sort_col = allowed_sort.get(sort_by, DisasterEvent.occurred_at)
    if sort_order == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    # Paginate
    offset = (page - 1) * page_size
    rows = query.offset(offset).limit(page_size).all()

    items = []
    for event, lat, lng in rows:
        event.lat = lat
        event.lng = lng
        items.append(_event_to_response(event))

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total > 0 else 0,
    }


def get_event_by_id(db: Session, event_id: UUID) -> EventResponse | None:
    row = (
        db.query(
            DisasterEvent,
            ST_Y(DisasterEvent.location).label("lat"),
            ST_X(DisasterEvent.location).label("lng"),
        )
        .filter(DisasterEvent.id == event_id)
        .first()
    )
    if not row:
        return None
    event, lat, lng = row
    event.lat = lat
    event.lng = lng
    return _event_to_response(event)


def update_event(db: Session, event_id: UUID, data: EventUpdate) -> EventResponse | None:
    event = db.query(DisasterEvent).filter(DisasterEvent.id == event_id).first()
    if not event:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(event, key, value)

    db.commit()
    db.refresh(event)
    return get_event_by_id(db, event_id)


def delete_event(db: Session, event_id: UUID) -> bool:
    event = db.query(DisasterEvent).filter(DisasterEvent.id == event_id).first()
    if not event:
        return False
    # 解除關聯通報（SET NULL）
    db.query(DisasterReport).filter(
        DisasterReport.event_id == event_id
    ).update({"event_id": None})
    db.delete(event)
    db.commit()
    return True


def get_map_events(
    db: Session,
    *,
    bounds: str | None = None,
    disaster_type: str | None = None,
    severity_min: int | None = None,
    status: str = "reported",
) -> list[dict]:
    query = db.query(
        DisasterEvent,
        ST_Y(DisasterEvent.location).label("lat"),
        ST_X(DisasterEvent.location).label("lng"),
    )

    if status:
        query = query.filter(DisasterEvent.status == status)
    if disaster_type:
        query = query.filter(DisasterEvent.disaster_type == disaster_type)
    if severity_min is not None:
        query = query.filter(DisasterEvent.severity >= severity_min)
    if bounds:
        parts = bounds.split(",")
        if len(parts) == 4:
            south, west, north, east = [float(p) for p in parts]
            envelope = func.ST_MakeEnvelope(west, south, east, north, 4326)
            query = query.filter(func.ST_Within(DisasterEvent.location, envelope))

    rows = query.all()
    items = []
    for event, lat, lng in rows:
        items.append(
            {
                "id": event.id,
                "title": event.title,
                "disaster_type": event.disaster_type,
                "severity": event.severity,
                "latitude": lat,
                "longitude": lng,
                "status": event.status,
                "report_count": event.report_count,
                "occurred_at": event.occurred_at,
                "location_approximate": event.location_approximate,
            }
        )
    return items


def update_event_location(
    db: Session, event_id: UUID, location_text: str, coords: dict
) -> EventMapItem | None:
    """Update event location coordinates and clear the approximate flag."""
    row = (
        db.query(
            DisasterEvent,
            ST_Y(DisasterEvent.location).label("lat"),
            ST_X(DisasterEvent.location).label("lng"),
        )
        .filter(DisasterEvent.id == event_id)
        .first()
    )
    if not row:
        return None
    event, _, _ = row

    point = ST_SetSRID(ST_MakePoint(coords["longitude"], coords["latitude"]), 4326)
    event.location = point
    event.location_text = location_text
    event.location_approximate = False
    db.commit()
    db.refresh(event)

    return EventMapItem(
        id=event.id,
        title=event.title,
        disaster_type=event.disaster_type,
        severity=event.severity,
        latitude=coords["latitude"],
        longitude=coords["longitude"],
        status=event.status,
        report_count=event.report_count,
        occurred_at=event.occurred_at,
        location_approximate=False,
    )

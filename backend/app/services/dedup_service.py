import difflib
from datetime import datetime, timedelta, timezone

from geoalchemy2.functions import ST_Distance, ST_DWithin, ST_SetSRID, ST_MakePoint
from sqlalchemy import cast
from sqlalchemy.orm import Session
from geoalchemy2 import Geography

from app.models.disaster_event import DisasterEvent

# Dedup radius by disaster type (in meters)
DEDUP_RADIUS = {
    "trapped":          1_000,   # 1 km
    "road_collapse":    2_000,   # 2 km
    "flooding":         5_000,   # 5 km
    "landslide":        3_000,   # 3 km
    "building_damage":  1_000,   # 1 km
    "utility_damage":   2_000,   # 2 km
    "fire":             1_000,   # 1 km
    "other":            3_000,   # 3 km
}

DEDUP_HOURS = 72


def find_candidate_events(
    db: Session,
    *,
    disaster_type: str,
    latitude: float,
    longitude: float,
) -> list[DisasterEvent]:
    """Find nearby active events of the same type within the dedup window."""
    radius = DEDUP_RADIUS.get(disaster_type, 10_000)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=DEDUP_HOURS)

    point = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)

    candidates = (
        db.query(DisasterEvent)
        .filter(
            DisasterEvent.status == "active",
            DisasterEvent.disaster_type == disaster_type,
            DisasterEvent.occurred_at >= cutoff,
            ST_DWithin(
                cast(DisasterEvent.location, Geography),
                cast(point, Geography),
                radius,
            ),
        )
        .order_by(
            ST_Distance(
                cast(DisasterEvent.location, Geography),
                cast(point, Geography),
            )
        )
        .limit(5)
        .all()
    )
    return candidates


def is_duplicate(new_report_desc: str, candidate_event: DisasterEvent) -> bool:
    """判斷新通報是否與候選事件重複（文字相似度）。"""
    candidate_text = f"{candidate_event.title} {candidate_event.description or ''}"
    ratio = difflib.SequenceMatcher(
        None, new_report_desc, candidate_text
    ).ratio()
    return ratio >= 0.4

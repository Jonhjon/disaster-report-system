import difflib
from datetime import datetime, timedelta, timezone
from math import atan2, cos, radians, sin, sqrt

import jieba
from geoalchemy2.functions import ST_Distance, ST_DWithin, ST_SetSRID, ST_MakePoint
from sqlalchemy import cast
from sqlalchemy.orm import Session
from geoalchemy2 import Geography

from app.config import settings
from app.models.disaster_event import DisasterEvent
from app.services.api_clients import get_anthropic_client

# Dedup radius by disaster type (in meters)
DEDUP_RADIUS = {
    "trapped":          50,    # 50m 單棟建築物
    "building_damage":  50,    # 50m 單棟建築物
    "fire":             150,   # 150m 延燒到鄰棟
    "road_collapse":    150,   # 150m 1~2 個街廓路段
    "utility_damage":   150,   # 150m 低壓設施影響範圍
    "flooding":         200,   # 200m 單條街道等級
    "small_landslide":  100,   # 100m 小型土石流
    # landslide 屬大型事件，不納入去重
    "other":            200,   # 200m 保守預設
}

# Dedup time window by disaster type (in hours); default for unlisted types
DEDUP_HOURS_BY_TYPE: dict[str, int] = {
    "fire": 6,
}
DEDUP_HOURS_DEFAULT = 48


def find_candidate_events(
    db: Session,
    *,
    disaster_type: str,
    latitude: float,
    longitude: float,
) -> list[DisasterEvent]:
    """Find nearby active events of the same type within the dedup window."""
    radius = DEDUP_RADIUS.get(disaster_type, 10_000)
    hours = DEDUP_HOURS_BY_TYPE.get(disaster_type, DEDUP_HOURS_DEFAULT)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    point = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)

    candidates = (
        db.query(DisasterEvent)
        .filter(
            DisasterEvent.status == "reported",
            DisasterEvent.disaster_type == disaster_type,
            DisasterEvent.updated_at >= cutoff,
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


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def _compute_dedup_score(
    new_desc: str,
    new_lat: float,
    new_lon: float,
    new_time: datetime,
    new_type: str,
    candidate: DisasterEvent,
) -> float:
    """Compute a 0–1 similarity score across four dimensions."""
    # 1. Semantic similarity: jieba tokenisation + Jaccard
    candidate_text = f"{candidate.title} {candidate.description or ''}"
    new_tokens = set(jieba.cut(new_desc))
    cand_tokens = set(jieba.cut(candidate_text))
    union = new_tokens | cand_tokens
    semantic_score = len(new_tokens & cand_tokens) / len(union) if union else 0.0

    # 2. Geographic distance score
    try:
        from geoalchemy2.shape import to_shape  # noqa: PLC0415
        pt = to_shape(candidate.location)
        cand_lat, cand_lon = pt.y, pt.x
        max_radius_km = DEDUP_RADIUS.get(new_type, 10_000) / 1000
        dist_km = _haversine_km(new_lat, new_lon, cand_lat, cand_lon)
        geo_score = max(0.0, 1.0 - dist_km / max_radius_km)
    except Exception:
        geo_score = 0.5  # fallback when geometry is unavailable (e.g. in tests)

    # 3. Time proximity score
    cand_time = candidate.occurred_at
    if cand_time.tzinfo is None:
        cand_time = cand_time.replace(tzinfo=timezone.utc)
    if new_time.tzinfo is None:
        new_time = new_time.replace(tzinfo=timezone.utc)
    hours_diff = abs((new_time - cand_time).total_seconds()) / 3600
    if hours_diff <= 1:
        time_score = 1.0
    elif hours_diff >= 24:
        time_score = 0.2
    else:
        time_score = 1.0 - 0.8 * (hours_diff - 1) / 23

    # 4. Type match score
    type_score = 1.0 if new_type == candidate.disaster_type else 0.0

    return 0.3 * semantic_score + 0.3 * geo_score + 0.2 * time_score + 0.2 * type_score


async def llm_judge_duplicate(new_desc: str, candidate: DisasterEvent) -> bool:
    """Use Claude haiku to judge whether two reports describe the same disaster event."""
    client = get_anthropic_client()
    candidate_text = f"{candidate.title}：{candidate.description or ''}"
    prompt = (
        "以下兩則通報是否描述同一個災害事件？請只回答 YES 或 NO。\n\n"
        f"通報一：{new_desc}\n\n"
        f"通報二：{candidate_text}"
    )
    try:
        message = await client.messages.create(
            model=settings.DEDUP_MODEL,
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip().upper().startswith("YES")
    except Exception:
        # Fallback to string similarity when LLM is unavailable
        candidate_full = f"{candidate.title} {candidate.description or ''}"
        ratio = difflib.SequenceMatcher(None, new_desc, candidate_full).ratio()
        return ratio >= 0.4


async def find_and_score_candidates(
    db: Session,
    *,
    disaster_type: str,
    description: str,
    latitude: float,
    longitude: float,
    occurred_at: datetime,
) -> list[dict]:
    """回傳 score >= 0.50 的候選事件及分數，依 score 降序排列。"""
    candidates = find_candidate_events(
        db,
        disaster_type=disaster_type,
        latitude=latitude,
        longitude=longitude,
    )

    scored: list[dict] = []
    for candidate in candidates:
        score = _compute_dedup_score(
            description, latitude, longitude, occurred_at, disaster_type, candidate,
        )
        if score >= 0.50:
            dist_km = _haversine_km(latitude, longitude, 0, 0)
            try:
                from geoalchemy2.shape import to_shape  # noqa: PLC0415
                pt = to_shape(candidate.location)
                dist_km = _haversine_km(latitude, longitude, pt.y, pt.x)
            except Exception:
                pass
            scored.append({
                "event": candidate,
                "score": score,
                "distance_m": round(dist_km * 1000),
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


async def is_duplicate(
    new_desc: str,
    new_lat: float,
    new_lon: float,
    new_time: datetime,
    new_type: str,
    candidate: DisasterEvent,
) -> bool:
    """判斷新通報是否與候選事件重複（多維度加權評分 + LLM 輔助）。

    Score > 0.80 → duplicate
    Score 0.50–0.80 → delegate to LLM
    Score < 0.50 → distinct event
    """
    score = _compute_dedup_score(new_desc, new_lat, new_lon, new_time, new_type, candidate)
    if score > 0.80:
        return True
    if score >= 0.50:
        return await llm_judge_duplicate(new_desc, candidate)
    return False

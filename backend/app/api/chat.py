import json
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.database import get_db
from app.models.disaster_event import DisasterEvent
from app.models.disaster_report import DisasterReport
from app.schemas.chat import ChatRequest
from app.services import llm_service
from app.services.dedup_service import find_candidate_events, is_duplicate
from app.services.geocoding_service import geocode_address
from geoalchemy2.functions import ST_SetSRID, ST_MakePoint

router = APIRouter()


async def _process_tool_use(tool_data: dict, raw_message: str, db: Session) -> dict:
    """Process the submit_disaster_report tool call: geocode, dedup, save."""
    latitude = tool_data.get("latitude")
    longitude = tool_data.get("longitude")

    # Geocoding if no coordinates
    geocoded_address = None
    if latitude is None or longitude is None:
        coords = await geocode_address(tool_data["location_text"])
        if coords:
            latitude = coords["latitude"]
            longitude = coords["longitude"]
            geocoded_address = coords.get("display_name")
        else:
            # Default to Taiwan center if geocoding fails
            latitude = latitude or 23.5
            longitude = longitude or 121.0

    # Parse occurred_at
    occurred_at_str = tool_data.get("occurred_at")
    if occurred_at_str:
        try:
            occurred_at = datetime.fromisoformat(occurred_at_str)
            if occurred_at.tzinfo is None:
                # LLM 以台灣時間為基準輸出，但不含時區資訊，補上 Asia/Taipei
                occurred_at = occurred_at.replace(tzinfo=ZoneInfo("Asia/Taipei"))
        except ValueError:
            occurred_at = datetime.now(timezone.utc)
    else:
        occurred_at = datetime.now(timezone.utc)

    # Deduplication
    candidates = find_candidate_events(
        db,
        disaster_type=tool_data["disaster_type"],
        latitude=latitude,
        longitude=longitude,
    )

    matched_event = None
    for candidate in candidates:
        if is_duplicate(tool_data["description"], candidate):
            matched_event = candidate
            break

    point = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)

    # Create report
    report = DisasterReport(
        reporter_name=tool_data.get("reporter_name"),
        reporter_phone=tool_data.get("reporter_phone"),
        raw_message=raw_message,
        extracted_data=tool_data,
        location=point,
        location_text=tool_data["location_text"],
    )

    if matched_event:
        # Update existing event
        matched_event.report_count += 1
        matched_event.severity = max(matched_event.severity, tool_data["severity"])
        matched_event.casualties = max(
            matched_event.casualties, tool_data.get("casualties", 0)
        )
        matched_event.injured = max(
            matched_event.injured, tool_data.get("injured", 0)
        )
        matched_event.trapped = max(
            matched_event.trapped, tool_data.get("trapped", 0)
        )
        matched_event.updated_at = datetime.now(timezone.utc)
        report.event_id = matched_event.id
        db.add(report)
        db.commit()
        return {
            "status": "merged",
            "event_id": str(matched_event.id),
            "message": f"此通報已合併至現有事件「{matched_event.title}」（第 {matched_event.report_count} 筆通報）",
            "geocoded_address": geocoded_address,
        }
    else:
        # Create new event
        disaster_type_names = {
            "trapped": "人員受困",
            "road_collapse": "路段崩塌",
            "flooding": "淹水",
            "landslide": "土石流",
            "building_damage": "建物受損",
            "utility_damage": "管線/電力受損",
            "fire": "火警",
            "other": "災情",
        }
        type_name = disaster_type_names.get(
            tool_data["disaster_type"], tool_data["disaster_type"]
        )
        title = f"{tool_data['location_text']}{type_name}"

        event = DisasterEvent(
            title=title,
            disaster_type=tool_data["disaster_type"],
            severity=tool_data["severity"],
            description=tool_data["description"],
            location_text=tool_data["location_text"],
            location=point,
            occurred_at=occurred_at,
            casualties=tool_data.get("casualties", 0),
            injured=tool_data.get("injured", 0),
            trapped=tool_data.get("trapped", 0),
        )
        db.add(event)
        db.flush()

        report.event_id = event.id
        db.add(report)
        db.commit()
        return {
            "status": "created",
            "event_id": str(event.id),
            "message": f"已建立新的災情事件「{title}」",
            "geocoded_address": geocoded_address,
        }


@router.post("/chat")
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    # Build messages for Claude
    messages = [{"role": m.role, "content": m.content} for m in request.history]
    messages.append({"role": "user", "content": request.message})

    # Collect raw message for report
    raw_message = "\n".join(
        f"[{m.role}] {m.content}" for m in request.history
    ) + f"\n[user] {request.message}"

    async def event_generator():
        try:
            async for chunk in llm_service.stream_chat(messages):
                if chunk["type"] == "text":
                    yield {"event": "message", "data": json.dumps(chunk, ensure_ascii=False)}
                elif chunk["type"] == "tool_use":
                    # Process the tool call
                    result = await _process_tool_use(chunk["data"], raw_message, db)
                    yield {
                        "event": "message",
                        "data": json.dumps(
                            {"type": "report_submitted", **result}, ensure_ascii=False
                        ),
                    }
                elif chunk["type"] == "done":
                    yield {"event": "message", "data": json.dumps({"type": "done"}, ensure_ascii=False)}
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                is_rpd = any(k in error_msg.lower() for k in ["per-day", "per_day", "daily"])
                if is_rpd:
                    friendly = "Gemini API 每日免費配額已用盡，請明天（UTC 00:00 重置）再試，或至 Google AI Studio 啟用付費方案。"
                else:
                    friendly = "AI 服務每分鐘請求超限（已等待重試），請稍等 1 分鐘後再試。"
            else:
                friendly = f"AI 服務發生錯誤，請稍後再試。（{error_msg[:120]}）"
            yield {"event": "message", "data": json.dumps({"type": "error", "message": friendly}, ensure_ascii=False)}

    return EventSourceResponse(event_generator())

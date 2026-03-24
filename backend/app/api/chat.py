import json
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

MAX_GEOCODING_RETRIES = 3


def _location_is_precise(location_text: str, coords: dict | None) -> bool:
    """True when the location can be resolved to a specific building.

    Two paths to precision:
    - Google Places returned a result (specific establishment found), OR
    - location_text has county/city + road + door number (號)
    """
    if coords and coords.get("source") == "google_places":
        return True
    text = location_text
    has_county = any(w in text for w in ["縣", "市"])
    has_road   = any(w in text for w in ["路", "街", "大道", "巷", "弄", "道"])
    has_number = "號" in text
    return has_county and has_road and has_number


def _location_hint(location_text: str) -> str:
    """Return a targeted follow-up question based on which address component is missing."""
    text = location_text
    has_county = any(w in text for w in ["縣", "市"])
    has_road = any(w in text for w in ["路", "街", "大道", "巷", "弄", "道"])
    has_number = "號" in text

    if not has_county:
        return "請問事發地點是哪個縣市？（例如：台北市、新北市、花蓮縣）"
    if not has_road:
        return "請問附近的路名或地標是什麼？（例如：中正路、捷運站、學校名稱）"
    if not has_number:
        return "請問門牌號碼或更精確的位置？（例如：123號，或附近明顯建築物）"
    return "請提供更具體的地址，例如縣市＋區＋路段＋門牌，或附近知名地標。"


async def _process_tool_use(
    tool_data: dict,
    raw_message: str,
    db: Session,
    coords: dict | None,
) -> dict:
    """Process the submit_disaster_report tool call: dedup, save.

    coords: pre-geocoded result from geocode_address(), or None if geocoding failed.
    When coords is None the event is created with location_approximate=True.
    """
    location_approximate = coords is None
    if coords:
        latitude = coords["latitude"]
        longitude = coords["longitude"]
        geocoded_address = coords.get("display_name")
    else:
        latitude = 23.5
        longitude = 121.0
        geocoded_address = None

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
        if await is_duplicate(
            tool_data["description"],
            latitude,
            longitude,
            occurred_at,
            tool_data["disaster_type"],
            candidate,
        ):
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
            location_approximate=location_approximate,
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
        def _sse(data: dict) -> dict:
            return {"event": "message", "data": json.dumps(data, ensure_ascii=False)}

        try:
            collected_text = ""
            is_continuation = False  # 已進入追問流程，避免無限遞迴

            # 計算歷史訊息中已失敗/不精確的 geocoding 次數（跨多輪對話）
            failed_attempts = sum(
                1 for m in messages
                if isinstance(m.get("content"), list)
                and any(
                    item.get("type") == "tool_result"
                    and (
                        "geocoding 失敗" in (item.get("content") or "")
                        or "地址不夠精確" in (item.get("content") or "")
                    )
                    for item in m["content"]
                )
            )

            async for chunk in llm_service.stream_chat(messages):
                if chunk["type"] == "text":
                    collected_text += chunk["content"]
                    yield _sse(chunk)

                elif chunk["type"] == "tool_use":
                    tool_data = chunk["data"]
                    tool_use_id = chunk["tool_use_id"]

                    # 嘗試 geocode
                    location = tool_data["location_text"]
                    coords = await geocode_address(location)
                    geocoding_ok = coords is not None
                    location_precise = _location_is_precise(location, coords)

                    if (not geocoding_ok or not location_precise) and not is_continuation and failed_attempts < MAX_GEOCODING_RETRIES:
                        # Geocoding 失敗或地址不夠精確且未超過重試上限 → 透過 tool_result 讓 Claude 追問使用者
                        assistant_content = []
                        if collected_text:
                            assistant_content.append({"type": "text", "text": collected_text})
                        assistant_content.append({
                            "type": "tool_use",
                            "id": tool_use_id,
                            "name": "submit_disaster_report",
                            "input": tool_data,
                        })
                        hint = _location_hint(location)
                        if not geocoding_ok:
                            reason = f"系統無法辨識地址「{location}」的確切位置（geocoding 失敗）。"
                        else:
                            reason = f"地址「{location}」尚未精確到建築物等級（地址不夠精確）。"
                        tool_result_msg = (
                            reason
                            + f"請向使用者追問：{hint}"
                            + "不要自行推測地址，必須等使用者提供更具體資訊後再重新提交通報。"
                        )
                        continuation_messages = messages + [
                            {"role": "assistant", "content": assistant_content},
                            {"role": "user", "content": [{
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "content": tool_result_msg,
                            }]},
                        ]
                        collected_text = ""
                        is_continuation = True
                        async for cont_chunk in llm_service.stream_chat(continuation_messages):
                            if cont_chunk["type"] == "text":
                                yield _sse(cont_chunk)
                            elif cont_chunk["type"] == "tool_use":
                                # Edge case：continuation 裡 Claude 又呼叫工具，強制接受
                                cont_coords = await geocode_address(cont_chunk["data"]["location_text"])
                                result = await _process_tool_use(cont_chunk["data"], raw_message, db, cont_coords)
                                yield _sse({"type": "report_submitted", **result})
                                break
                            elif cont_chunk["type"] == "done":
                                yield _sse({"type": "done"})
                    else:
                        # Geocoding 成功、已在 continuation 中、或超過重試上限 → 建立事件
                        # coords 為 None 時將以 location_approximate=True 建立
                        result = await _process_tool_use(tool_data, raw_message, db, coords)
                        yield _sse({"type": "report_submitted", **result})

                elif chunk["type"] == "done":
                    if not is_continuation:
                        yield _sse({"type": "done"})

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                is_rpd = any(k in error_msg.lower() for k in ["per-day", "per_day", "daily"])
                if is_rpd:
                    friendly = "API 每日免費配額已用盡，請明天（UTC 00:00 重置）再試，或至 Google AI Studio 啟用付費方案。"
                else:
                    friendly = "AI 服務每分鐘請求超限（已等待重試），請稍等 1 分鐘後再試。"
            else:
                friendly = f"AI 服務發生錯誤，請稍後再試。（{error_msg[:120]}）"
            yield _sse({"type": "error", "message": friendly})

    return EventSourceResponse(event_generator(), ping=15)

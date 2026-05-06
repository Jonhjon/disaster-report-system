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
from app.schemas.llm_tools import SubmitDisasterReportPayload
from app.services import llm_service
from app.services.dedup_service import find_and_score_candidates
from app.services.geocoding_service import (
    TAIWAN_CENTER_LAT,
    TAIWAN_CENTER_LON,
    geocode_address,
)
from app.services.llm_service import (
    merge_event_descriptions,
    reextract_numbers_from_description,
)
from geoalchemy2.functions import ST_SetSRID, ST_MakePoint

router = APIRouter()

MAX_GEOCODING_RETRIES = 3

# submit_disaster_report 帶 merge_event_id 時，允許合併進去的事件狀態。
_MERGEABLE_EVENT_STATUSES = frozenset({"reported"})


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
        return "請問附近的路名或地標是什麼？（例如:中正路、捷運站、學校名稱）"
    if not has_number:
        return "請問門牌號碼或更精確的位置？（例如：123號，或附近明顯建築物）"
    return "請提供更具體的地址，例如縣市＋區＋路段＋門牌，或附近知名地標。"


def _format_candidates_hint(candidates: list[dict]) -> str:
    """將候選地點清單格式化為供 LLM 詢問使用者的提示文字。"""
    lines = ["系統在附近找到多個符合地點，請向使用者確認是哪一個："]
    for i, c in enumerate(candidates, 1):
        dist = c.get("distance_m", "?")
        lines.append(f"{i}. {c['name']}（{c['address']}，距離約 {dist} 公尺）")
    lines.append("請列出選項讓使用者選擇編號，使用者確認後以正確名稱重新提交通報。")
    return "\n".join(lines)


def _build_candidates_selection_event(candidates: list[dict]) -> dict:
    """將候選事件清單打包為 candidates_selection SSE 事件，供前端渲染卡片。"""
    return {
        "type": "candidates_selection",
        "candidates": [
            {
                "event_id": c["event_id"],
                "title": c["title"],
                "description": c["description"],
                "location_text": c["location_text"],
                "report_count": c["report_count"],
                "distance_m": c["distance_m"],
                "score": c["score"],
            }
            for c in candidates
        ],
    }


def _format_dedup_candidates_hint(candidates: list[dict]) -> str:
    """將相似事件候選清單格式化為供 LLM 詢問使用者的提示文字。"""
    lines = [
        "系統偵測到附近已有相似的災情事件，請向使用者列出以下選項，讓使用者選擇要合併到哪個既有事件或建立新事件："
    ]
    for i, c in enumerate(candidates, 1):
        lines.append(
            f"{i}. 「{c['title']}」— {c['description'][:50] if c.get('description') else '無描述'}"
            f"（地點：{c['location_text']}，目前 {c['report_count']} 筆通報，"
            f"距離約 {c['distance_m']} 公尺，相似度 {c['score']:.0%}）"
            f"  [event_id: {c['event_id']}]"
        )
    lines.append(f"{len(candidates) + 1}. 建立全新事件（此通報與上述事件無關）")
    lines.append("")
    lines.append(
        "請以自然語言列出選項讓使用者選擇。使用者選擇後，"
        "再次呼叫 submit_disaster_report 並設定 merge_event_id 為對應事件的 UUID，"
        "或填入 'new' 建立新事件。"
    )
    return "\n".join(lines)


async def _merge_into_event(
    target_event: DisasterEvent,
    tool_data: SubmitDisasterReportPayload,
    raw_message: str,
    db: Session,
    coords: dict | None,
) -> dict:
    """將新通報合併到指定的既有事件。"""
    geocoded_address = coords.get("display_name") if coords else None
    if coords:
        latitude = coords["latitude"]
        longitude = coords["longitude"]
    else:
        latitude = TAIWAN_CENTER_LAT
        longitude = TAIWAN_CENTER_LON
    point = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)

    # 使用 SQL column expression 達成 atomic increment，避免並發合併時 lost update
    target_event.report_count = DisasterEvent.report_count + 1

    # 合併描述：用 LLM 整合兩段描述，保留完整脈絡
    new_description = (tool_data.description or "").strip()
    if new_description:
        try:
            target_event.description = await merge_event_descriptions(
                target_event.description or "", new_description
            )
        except Exception:
            target_event.description = (
                f"{target_event.description}；{new_description}"
                if target_event.description
                else new_description
            )

    # 從合併後的描述重新萃取數字，讓 LLM 從完整脈絡判斷累計傷亡
    try:
        extracted = await reextract_numbers_from_description(target_event.description or "")
    except Exception:
        extracted = {}

    if extracted:
        if "casualties" in extracted:
            target_event.casualties = extracted["casualties"]
        if "injured" in extracted:
            target_event.injured = extracted["injured"]
        if "trapped" in extracted:
            target_event.trapped = extracted["trapped"]
        if "severity" in extracted:
            target_event.severity = max(target_event.severity, extracted["severity"])
        else:
            target_event.severity = max(target_event.severity, tool_data.severity)
    else:
        target_event.casualties = DisasterEvent.casualties + tool_data.casualties
        target_event.injured = DisasterEvent.injured + tool_data.injured
        target_event.trapped = DisasterEvent.trapped + tool_data.trapped
        target_event.severity = max(target_event.severity, tool_data.severity)

    # 若新通報提供更精確的 location_text，則更新
    new_loc = (tool_data.location_text or "").strip()
    if new_loc and new_loc != (target_event.location_text or ""):
        if _location_is_precise(new_loc, None) and not _location_is_precise(
            target_event.location_text or "", None
        ):
            target_event.location_text = new_loc

    target_event.updated_at = datetime.now(timezone.utc)

    report = DisasterReport(
        reporter_name=tool_data.reporter_name,
        reporter_phone=tool_data.reporter_phone,
        raw_message=raw_message,
        extracted_data=tool_data.model_dump(),
        location=point,
        location_text=tool_data.location_text,
        event_id=target_event.id,
    )
    db.add(report)
    db.commit()
    return {
        "status": "merged",
        "event_id": str(target_event.id),
        "message": f"此通報已合併至現有事件「{target_event.title}」（第 {target_event.report_count} 筆通報）",
        "geocoded_address": geocoded_address,
    }


def _create_new_event(
    tool_data: SubmitDisasterReportPayload,
    raw_message: str,
    db: Session,
    coords: dict | None,
    occurred_at: datetime,
) -> dict:
    """建立全新的災情事件。"""
    location_approximate = coords is None
    geocoded_address = coords.get("display_name") if coords else None
    if coords:
        latitude = coords["latitude"]
        longitude = coords["longitude"]
    else:
        latitude = TAIWAN_CENTER_LAT
        longitude = TAIWAN_CENTER_LON
    point = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)

    disaster_type_names = {
        "trapped": "人員受困",
        "road_collapse": "路段崩塌",
        "flooding": "淹水",
        "landslide": "土石流",
        "small_landslide": "小型土石流",
        "building_damage": "建物受損",
        "utility_damage": "管線/電力受損",
        "fire": "火警",
        "other": "災情",
    }
    type_name = disaster_type_names.get(
        tool_data.disaster_type, tool_data.disaster_type
    )
    title = f"{tool_data.location_text}{type_name}"

    event = DisasterEvent(
        title=title,
        disaster_type=tool_data.disaster_type,
        severity=tool_data.severity,
        description=tool_data.description,
        location_text=tool_data.location_text,
        location=point,
        occurred_at=occurred_at,
        casualties=tool_data.casualties,
        injured=tool_data.injured,
        trapped=tool_data.trapped,
        location_approximate=location_approximate,
        status="reported",
    )
    db.add(event)
    db.flush()

    report = DisasterReport(
        reporter_name=tool_data.reporter_name,
        reporter_phone=tool_data.reporter_phone,
        raw_message=raw_message,
        extracted_data=tool_data.model_dump(),
        location=point,
        location_text=tool_data.location_text,
        event_id=event.id,
    )
    db.add(report)
    db.flush()

    db.commit()
    return {
        "status": "created",
        "event_id": str(event.id),
        "message": f"已建立新的災情事件「{title}」",
        "geocoded_address": geocoded_address,
    }


async def _process_tool_use(
    tool_data: SubmitDisasterReportPayload,
    raw_message: str,
    db: Session,
    coords: dict | None,
) -> dict:
    """Process the submit_disaster_report tool call."""
    if coords:
        latitude = coords["latitude"]
        longitude = coords["longitude"]
        geocoded_address = coords.get("display_name")
    else:
        latitude = TAIWAN_CENTER_LAT
        longitude = TAIWAN_CENTER_LON
        geocoded_address = None

    if tool_data.occurred_at:
        try:
            occurred_at = datetime.fromisoformat(tool_data.occurred_at)
            if occurred_at.tzinfo is None:
                occurred_at = occurred_at.replace(tzinfo=ZoneInfo("Asia/Taipei"))
        except ValueError:
            occurred_at = datetime.now(timezone.utc)
    else:
        occurred_at = datetime.now(timezone.utc)

    merge_event_id = tool_data.merge_event_id

    if merge_event_id is not None:
        if merge_event_id == "new":
            return _create_new_event(tool_data, raw_message, db, coords, occurred_at)

        target_event = db.get(DisasterEvent, merge_event_id)
        if target_event is None:
            return {
                "status": "error",
                "message": f"找不到事件 {merge_event_id}，該事件可能不存在。",
            }
        if target_event.status not in _MERGEABLE_EVENT_STATUSES:
            return {
                "status": "error",
                "message": f"事件「{target_event.title}」已結案，不可合併新通報。",
            }
        return await _merge_into_event(target_event, tool_data, raw_message, db, coords)

    scored_candidates = await find_and_score_candidates(
        db,
        disaster_type=tool_data.disaster_type,
        description=tool_data.description,
        latitude=latitude,
        longitude=longitude,
        occurred_at=occurred_at,
    )

    if scored_candidates:
        candidates_info = [
            {
                "event_id": str(c["event"].id),
                "title": c["event"].title,
                "description": c["event"].description or "",
                "location_text": c["event"].location_text,
                "report_count": c["event"].report_count,
                "distance_m": c["distance_m"],
                "score": c["score"],
            }
            for c in scored_candidates
        ]
        return {
            "status": "needs_user_choice",
            "candidates": candidates_info,
            "geocoded_address": geocoded_address,
        }

    return _create_new_event(tool_data, raw_message, db, coords, occurred_at)


@router.post("/chat")
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    history_from_request = [
        {"role": m.role, "content": m.content} for m in request.history
    ]
    messages = history_from_request + [{"role": "user", "content": request.message}]

    raw_message = "\n".join(
        f"[{m.role}] {m.content}" for m in request.history
    ) + f"\n[user] {request.message}"

    async def event_generator():
        def _sse(data: dict) -> dict:
            return {"event": "message", "data": json.dumps(data, ensure_ascii=False)}

        async def _dedup_continuation(result: dict, tool_payload: SubmitDisasterReportPayload, tool_use_id: str, ctx_msgs: list):
            yield _sse(_build_candidates_selection_event(result["candidates"]))
            dedup_hint = _format_dedup_candidates_hint(result["candidates"])
            dedup_msgs = ctx_msgs + [
                {"role": "assistant", "content": [
                    {"type": "tool_use", "id": tool_use_id,
                     "name": "submit_disaster_report", "input": tool_payload.model_dump()}
                ]},
                {"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": tool_use_id, "content": dedup_hint}
                ]},
            ]
            async for dc in llm_service.stream_chat(dedup_msgs):
                if dc["type"] == "text":
                    yield _sse(dc)
                elif dc["type"] == "tool_use":
                    dc_payload = SubmitDisasterReportPayload.model_validate(dc["data"])
                    dc_coords = await geocode_address(dc_payload.location_text)
                    dc_result = await _process_tool_use(dc_payload, raw_message, db, dc_coords)
                    yield _sse({"type": "report_submitted", **dc_result})
                    break
                elif dc["type"] == "done":
                    yield _sse({"type": "done"})

        try:
            collected_text = ""
            is_continuation = False

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
                    tool_payload = SubmitDisasterReportPayload.model_validate(chunk["data"])
                    tool_use_id = chunk["tool_use_id"]

                    location = tool_payload.location_text
                    coords = await geocode_address(location)
                    geocoding_ok = coords is not None
                    location_precise = _location_is_precise(location, coords)

                    candidates_list = coords.get("candidates") if coords else None
                    need_disambiguation = (
                        bool(candidates_list) and len(candidates_list) > 1
                        and not is_continuation
                        and failed_attempts < MAX_GEOCODING_RETRIES
                    )

                    if need_disambiguation:
                        assistant_content = []
                        if collected_text:
                            assistant_content.append({"type": "text", "text": collected_text})
                        assistant_content.append({
                            "type": "tool_use",
                            "id": tool_use_id,
                            "name": "submit_disaster_report",
                            "input": tool_payload.model_dump(),
                        })
                        tool_result_msg = _format_candidates_hint(candidates_list)
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
                                cont_payload = SubmitDisasterReportPayload.model_validate(cont_chunk["data"])
                                cont_coords = await geocode_address(cont_payload.location_text)
                                result = await _process_tool_use(cont_payload, raw_message, db, cont_coords)
                                if result["status"] == "needs_user_choice":
                                    async for evt in _dedup_continuation(
                                        result, cont_payload, cont_chunk["tool_use_id"],
                                        continuation_messages,
                                    ):
                                        yield evt
                                else:
                                    yield _sse({"type": "report_submitted", **result})
                                break
                            elif cont_chunk["type"] == "done":
                                yield _sse({"type": "done"})
                    elif (not geocoding_ok or not location_precise) and not is_continuation and failed_attempts < MAX_GEOCODING_RETRIES:
                        assistant_content = []
                        if collected_text:
                            assistant_content.append({"type": "text", "text": collected_text})
                        assistant_content.append({
                            "type": "tool_use",
                            "id": tool_use_id,
                            "name": "submit_disaster_report",
                            "input": tool_payload.model_dump(),
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
                                cont_payload = SubmitDisasterReportPayload.model_validate(cont_chunk["data"])
                                cont_coords = await geocode_address(cont_payload.location_text)
                                result = await _process_tool_use(cont_payload, raw_message, db, cont_coords)
                                if result["status"] == "needs_user_choice":
                                    async for evt in _dedup_continuation(
                                        result, cont_payload, cont_chunk["tool_use_id"],
                                        continuation_messages,
                                    ):
                                        yield evt
                                else:
                                    yield _sse({"type": "report_submitted", **result})
                                break
                            elif cont_chunk["type"] == "done":
                                yield _sse({"type": "done"})
                    else:
                        result = await _process_tool_use(tool_payload, raw_message, db, coords)

                        if result["status"] == "needs_user_choice" and not is_continuation:
                            yield _sse(_build_candidates_selection_event(result["candidates"]))

                            assistant_content = []
                            if collected_text:
                                assistant_content.append({"type": "text", "text": collected_text})
                            assistant_content.append({
                                "type": "tool_use",
                                "id": tool_use_id,
                                "name": "submit_disaster_report",
                                "input": tool_payload.model_dump(),
                            })
                            dedup_hint = _format_dedup_candidates_hint(result["candidates"])
                            continuation_messages = messages + [
                                {"role": "assistant", "content": assistant_content},
                                {"role": "user", "content": [{
                                    "type": "tool_result",
                                    "tool_use_id": tool_use_id,
                                    "content": dedup_hint,
                                }]},
                            ]
                            collected_text = ""
                            is_continuation = True
                            async for cont_chunk in llm_service.stream_chat(continuation_messages):
                                if cont_chunk["type"] == "text":
                                    yield _sse(cont_chunk)
                                elif cont_chunk["type"] == "tool_use":
                                    cont_payload = SubmitDisasterReportPayload.model_validate(cont_chunk["data"])
                                    cont_coords = await geocode_address(cont_payload.location_text)
                                    cont_result = await _process_tool_use(
                                        cont_payload, raw_message, db, cont_coords,
                                    )
                                    yield _sse({"type": "report_submitted", **cont_result})
                                    break
                                elif cont_chunk["type"] == "done":
                                    yield _sse({"type": "done"})
                        else:
                            yield _sse({"type": "report_submitted", **result})

                elif chunk["type"] == "done":
                    if not is_continuation:
                        yield _sse({"type": "done"})

        except Exception as e:
            try:
                db.rollback()
            except Exception:
                pass
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

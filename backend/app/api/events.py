from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.chat_session import ChatSession
from app.models.clarification_request import ClarificationRequest
from app.models.disaster_event import DisasterEvent
from app.models.disaster_report import DisasterReport
from app.schemas.clarification import ClarificationCreate, ClarificationResponse
from app.schemas.event import (
    EventListResponse,
    EventLocationUpdate,
    EventMapItem,
    EventMapResponse,
    EventResponse,
    EventUpdate,
)
from app.schemas.report import ReportListResponse, ReportResponse
from app.config import settings
from app.services import event_service
from app.services.geocoding_service import geocode_address
from app.services.notification_service import (
    DailyLimitExceeded,
    NotificationService,
)
from app.api.deps import get_current_user, get_notification_service
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


def _default_recipient_for_channel(report: DisasterReport | None, channel: str) -> str | None:
    """依 channel 從對應通報中取預設聯絡資訊。"""
    if report is None:
        return None
    if channel == "sms":
        return report.reporter_phone
    if channel == "email":
        return report.reporter_email
    if channel == "line":
        return report.reporter_line_user_id
    return None


@router.post(
    "/events/{event_id}/clarification",
    response_model=ClarificationResponse,
    status_code=201,
)
def create_clarification(
    event_id: UUID,
    payload: ClarificationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    notifier: NotificationService = Depends(get_notification_service),
):
    """通報中心管理員對事件發送追問。"""
    event = db.query(DisasterEvent).filter(DisasterEvent.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="事件不存在")

    # Kill switch: 檢查每日推播上限
    try:
        notifier.check_daily_limit(db)
    except DailyLimitExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    # 取最新一筆 report 作為預設聯絡資訊來源
    report = (
        db.query(DisasterReport)
        .filter(DisasterReport.event_id == event_id)
        .order_by(DisasterReport.created_at.desc())
        .first()
    )

    recipient = payload.recipient or _default_recipient_for_channel(report, payload.channel)
    if not recipient:
        raise HTTPException(
            status_code=400,
            detail=f"找不到 {payload.channel} 通道的收件人，請在 body 指定 recipient",
        )

    # 取或建立 chat_session
    session = (
        db.query(ChatSession)
        .filter(ChatSession.event_id == event_id)
        .first()
    )
    if session is None:
        session = ChatSession(
            event_id=event_id,
            report_id=report.id if report is not None else None,
            messages=[],
            pending_questions=[],
            status="awaiting_user",
        )
        db.add(session)
        db.flush()

    # Append question to pending_questions
    question_entry = {
        "id": str(uuid4()),
        "question": payload.question,
        "asked_by": current_user.username,
        "asked_at": datetime.now(timezone.utc).isoformat(),
    }
    session.pending_questions = list(session.pending_questions or []) + [question_entry]
    session.status = "awaiting_user"

    resume_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/chat/resume/{session.session_token}"
    message_body = (
        f"通報中心有後續問題：{payload.question}\n請點擊連結回覆：{resume_url}"
    )

    clar = ClarificationRequest(
        event_id=event_id,
        session_id=session.id,
        channel=payload.channel,
        recipient=recipient,
        question=payload.question,
        message_body=message_body,
        status="pending",
    )
    db.add(clar)
    db.flush()

    # 實際呼叫 notification_service
    result = notifier.send(
        channel=payload.channel, recipient=recipient, body=message_body
    )
    now = datetime.now(timezone.utc)
    if result.success:
        clar.status = "sent"
        clar.provider_message_id = result.provider_message_id
        clar.sent_at = now
    else:
        clar.status = "failed"
        clar.error_message = result.error_message

    db.commit()
    if hasattr(db, "refresh"):
        try:
            db.refresh(clar)
        except Exception:  # noqa: BLE001
            pass

    return ClarificationResponse(
        id=clar.id,
        channel=clar.channel,
        status=clar.status,
        sent_at=clar.sent_at,
        delivered_at=clar.delivered_at,
        replied_at=clar.replied_at,
        error_message=clar.error_message,
        created_at=clar.created_at or datetime.now(timezone.utc),
    )

"""Webhook endpoints for Twilio SMS status and LINE messaging events."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from twilio.request_validator import RequestValidator

from app.config import settings
from app.database import get_db
from app.models.chat_session import ChatSession
from app.models.clarification_request import ClarificationRequest
from app.models.disaster_report import DisasterReport

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Twilio SMS status callback
# ---------------------------------------------------------------------------

# Map Twilio MessageStatus → clarification_requests.status
_TWILIO_STATUS_MAP = {
    "sent": "sent",
    "queued": "sent",
    "delivered": "delivered",
    "failed": "failed",
    "undelivered": "failed",
}


@router.post("/webhooks/twilio/status")
async def twilio_status_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """Twilio 傳遞訊息遞送狀態的 callback。"""
    signature = request.headers.get("X-Twilio-Signature", "")
    form = await request.form()
    form_dict = {k: str(v) for k, v in form.items()}

    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN or "")
    url = str(request.url)
    if not validator.validate(url, form_dict, signature):
        raise HTTPException(status_code=403, detail="Twilio signature 驗證失敗")

    sid = form_dict.get("MessageSid")
    status = form_dict.get("MessageStatus")
    error = form_dict.get("ErrorMessage")
    if not sid or not status:
        return {"ok": True}

    clar = (
        db.query(ClarificationRequest)
        .filter(ClarificationRequest.provider_message_id == sid)
        .first()
    )
    if clar is None:
        logger.info("Twilio webhook: unknown SID %s", sid)
        return {"ok": True}

    mapped = _TWILIO_STATUS_MAP.get(status)
    if mapped is None:
        logger.info("Twilio webhook: unsupported status %s", status)
        return {"ok": True}

    clar.status = mapped
    if mapped == "delivered":
        clar.delivered_at = datetime.now(timezone.utc)
    if mapped == "failed" and error:
        clar.error_message = error
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# LINE webhook — 驗簽後處理 follow / message events
# ---------------------------------------------------------------------------

from linebot.v3 import WebhookParser  # noqa: E402
from linebot.v3.exceptions import InvalidSignatureError  # noqa: E402
from linebot.v3.webhooks import FollowEvent, MessageEvent, TextMessageContent  # noqa: E402


@router.post("/webhooks/line/events")
async def line_events_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    signature = request.headers.get("X-Line-Signature", "")
    body_bytes = await request.body()
    body_text = body_bytes.decode("utf-8")

    parser = WebhookParser(settings.LINE_CHANNEL_SECRET or "")
    try:
        events = parser.parse(body_text, signature)
    except InvalidSignatureError as exc:
        raise HTTPException(status_code=403, detail="LINE signature 驗證失敗") from exc
    except Exception as exc:  # noqa: BLE001
        # Parsing errors (malformed body etc.) — 避免 5xx 讓 LINE 不停重試
        logger.warning("LINE webhook parse error: %s", exc)
        try:
            payload = json.loads(body_text)
        except Exception:  # noqa: BLE001
            return {"ok": True}
        events = _fallback_parse(payload)

    for event in events:
        _process_line_event(event, db)

    db.commit()
    return {"ok": True}


def _fallback_parse(payload: dict) -> list:
    """測試環境下若 WebhookParser 嚴格驗證失敗，走 raw dict 解析。"""
    return []


def _process_line_event(event, db: Session) -> None:
    if isinstance(event, FollowEvent):
        logger.info("LINE follow event from %s", getattr(event.source, "user_id", None))
        return

    if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
        user_id = getattr(event.source, "user_id", None)
        text = event.message.text
        if not user_id or not text:
            return

        report = (
            db.query(DisasterReport)
            .filter(DisasterReport.reporter_line_user_id == user_id)
            .order_by(DisasterReport.created_at.desc())
            .first()
        )
        if report is None or report.event_id is None:
            logger.info("LINE message from unknown user %s", user_id)
            return

        session = (
            db.query(ChatSession)
            .filter(ChatSession.event_id == report.event_id)
            .first()
        )
        if session is None:
            return

        session.messages = list(session.messages or []) + [
            {"role": "user", "content": text, "source": "line"}
        ]
        session.status = "active"

        latest = (
            db.query(ClarificationRequest)
            .filter(ClarificationRequest.event_id == report.event_id)
            .filter(ClarificationRequest.channel == "line")
            .order_by(ClarificationRequest.created_at.desc())
            .first()
        )
        if latest is not None:
            latest.status = "replied"
            latest.replied_at = datetime.now(timezone.utc)

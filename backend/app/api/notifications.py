"""管理中心即時推播 SSE 端點。

EventSource API 不支援自訂 header，所以 token 改透過 query string 傳遞。
本端點只做認證後訂閱 broker，將 NewEventNotification 轉發成 SSE 事件。
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.services.notification_broker import (
    NewEventNotification,
    NotificationBroker,
    get_broker,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# SSE keep-alive 與 ping 區間（秒）
_QUEUE_WAIT_TIMEOUT = 15.0


def _get_user_from_query_token(token: str, db: Session) -> User:
    """從 query string 讀 JWT 並驗證使用者。"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="無效的認證憑證",
    )
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def _serialize_notification(notif: NewEventNotification) -> dict:
    """轉成 SSE event dict — 抽出方便單元測試。"""
    return {
        "event": "new_event",
        "data": json.dumps(asdict(notif), ensure_ascii=False),
    }


async def build_notification_stream(
    broker: NotificationBroker,
    queue_wait_timeout: float = _QUEUE_WAIT_TIMEOUT,
):
    """建立 SSE event generator。獨立函式以便單元測試。"""
    queue = await broker.subscribe()
    try:
        yield {"event": "ready", "data": "ok"}
        while True:
            try:
                notif = await asyncio.wait_for(queue.get(), timeout=queue_wait_timeout)
                yield _serialize_notification(notif)
            except asyncio.TimeoutError:
                # keep-alive；確保 proxy / 負載平衡器中的 idle timeout 不會切斷連線。
                yield {"event": "ping", "data": ""}
    finally:
        await broker.unsubscribe(queue)


@router.get("/admin/notifications/stream")
async def admin_notification_stream(
    token: str = Query(..., description="JWT access token"),
    db: Session = Depends(get_db),
):
    """管理員即時通知 SSE：訂閱 NotificationBroker，收到新事件即推播。"""
    user = _get_user_from_query_token(token, db)
    logger.info("admin notification SSE connected: user=%s", user.username)

    return EventSourceResponse(build_notification_stream(get_broker()), ping=15)

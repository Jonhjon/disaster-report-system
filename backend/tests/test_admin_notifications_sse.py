"""管理中心 SSE 推播端點整合測試。"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.api.notifications import build_notification_stream
from app.config import settings
from app.services.auth_service import create_access_token
from app.services.notification_broker import (
    NewEventNotification,
    NotificationBroker,
    get_broker,
)


def _make_notification(event_id: str = "evt-test-1") -> NewEventNotification:
    return NewEventNotification(
        event_id=event_id,
        title="測試火警",
        disaster_type="fire",
        severity=4,
        location_text="台北市信義區",
        occurred_at="2026-05-08T10:00:00+00:00",
    )


# ── 端點認證測試（HTTP 層） ──────────────────────────────────────────────

def test_sse_endpoint_requires_token(client):
    """缺 token → FastAPI 422 (必填 query)。"""
    response = client.get("/api/admin/notifications/stream")
    assert response.status_code in (401, 422)


def test_sse_endpoint_rejects_invalid_token(client):
    response = client.get("/api/admin/notifications/stream?token=not-a-valid-jwt")
    assert response.status_code == 401


def test_sse_endpoint_rejects_expired_token(client, mock_db, test_user):
    mock_query = mock_db.query.return_value
    mock_query.filter.return_value.first.return_value = test_user

    expired_payload = {
        "sub": test_user.username,
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
    }
    expired_token = jwt.encode(
        expired_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )

    response = client.get(f"/api/admin/notifications/stream?token={expired_token}")
    assert response.status_code == 401


def test_sse_endpoint_rejects_unknown_user(client, mock_db):
    """token 合法但使用者不存在於 DB（已被刪除）→ 401。"""
    mock_query = mock_db.query.return_value
    mock_query.filter.return_value.first.return_value = None

    token = create_access_token({"sub": "ghost"})
    response = client.get(f"/api/admin/notifications/stream?token={token}")
    assert response.status_code == 401


def test_sse_endpoint_rejects_inactive_user(client, mock_db, test_user):
    test_user.is_active = False
    mock_query = mock_db.query.return_value
    mock_query.filter.return_value.first.return_value = test_user

    token = create_access_token({"sub": test_user.username})
    response = client.get(f"/api/admin/notifications/stream?token={token}")
    assert response.status_code == 401


# ── Generator 行為測試（直接驅動 broker） ──────────────────────────────

@pytest.mark.asyncio
async def test_stream_emits_ready_then_published_event():
    """訂閱後第一筆是 ready，broker.publish 後送出 new_event。"""
    broker = NotificationBroker()
    gen = build_notification_stream(broker, queue_wait_timeout=0.5)

    # 第一筆：ready
    first = await asyncio.wait_for(gen.__anext__(), timeout=1.0)
    assert first["event"] == "ready"

    # publish 後第二筆：new_event
    notif = _make_notification("evt-stream-1")
    await broker.publish(notif)

    second = await asyncio.wait_for(gen.__anext__(), timeout=1.0)
    assert second["event"] == "new_event"
    payload = json.loads(second["data"])
    assert payload["event_id"] == "evt-stream-1"
    assert payload["title"] == notif.title
    assert payload["severity"] == notif.severity
    assert payload["location_text"] == notif.location_text

    await gen.aclose()


@pytest.mark.asyncio
async def test_stream_emits_ping_on_idle():
    """無訊息且 timeout 到期 → 送 ping 而非 hang。"""
    broker = NotificationBroker()
    gen = build_notification_stream(broker, queue_wait_timeout=0.1)

    ready = await asyncio.wait_for(gen.__anext__(), timeout=1.0)
    assert ready["event"] == "ready"

    ping = await asyncio.wait_for(gen.__anext__(), timeout=1.0)
    assert ping["event"] == "ping"

    await gen.aclose()


@pytest.mark.asyncio
async def test_stream_unsubscribes_on_close():
    """generator 結束後應從 broker 反訂閱。"""
    broker = NotificationBroker()
    assert await broker.subscriber_count() == 0

    gen = build_notification_stream(broker, queue_wait_timeout=0.1)
    await asyncio.wait_for(gen.__anext__(), timeout=1.0)  # ready
    assert await broker.subscriber_count() == 1

    await gen.aclose()
    assert await broker.subscriber_count() == 0


@pytest.mark.asyncio
async def test_global_broker_is_singleton():
    """get_broker() 多次呼叫應回傳同一物件。"""
    assert get_broker() is get_broker()

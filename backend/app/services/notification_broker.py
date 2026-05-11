"""管理中心即時推播：in-process broker。

設計：
- 每個 SSE 訂閱者持有一個 asyncio.Queue；publish 時以 put_nowait 廣播。
- 隊列上限 64，滿載時丟棄最舊訊息（fail-fast），避免慢消費者拖垮整個事件迴圈。
- 單一 uvicorn worker 部署成立。多 worker 部署需改用 Redis pub/sub。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_QUEUE_MAXSIZE = 64


@dataclass(frozen=True)
class NewEventNotification:
    """新事件通知 payload（送至管理中心 SSE）。"""

    event_id: str
    title: str
    disaster_type: str
    severity: int
    location_text: str
    occurred_at: str  # ISO-8601 字串，方便序列化


class NotificationBroker:
    """單一進程內 server→client 廣播器。"""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[NewEventNotification]] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue[NewEventNotification]:
        queue: asyncio.Queue[NewEventNotification] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        async with self._lock:
            self._subscribers.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[NewEventNotification]) -> None:
        async with self._lock:
            self._subscribers.discard(queue)

    async def publish(self, notification: NewEventNotification) -> None:
        async with self._lock:
            subscribers = list(self._subscribers)
        for q in subscribers:
            try:
                q.put_nowait(notification)
            except asyncio.QueueFull:
                logger.warning(
                    "notification queue full (size=%d), dropping message for one subscriber",
                    _QUEUE_MAXSIZE,
                )

    async def subscriber_count(self) -> int:
        async with self._lock:
            return len(self._subscribers)


_broker = NotificationBroker()


def get_broker() -> NotificationBroker:
    """回傳全域單例 broker。"""
    return _broker

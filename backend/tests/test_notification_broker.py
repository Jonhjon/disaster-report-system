"""NotificationBroker 單元測試。"""

from __future__ import annotations

import asyncio

import pytest

from app.services.notification_broker import (
    NewEventNotification,
    NotificationBroker,
)


def _make_notification(event_id: str = "abc-123") -> NewEventNotification:
    return NewEventNotification(
        event_id=event_id,
        title="測試事件",
        disaster_type="fire",
        severity=3,
        location_text="台北市信義區",
        occurred_at="2026-05-08T10:00:00+00:00",
    )


@pytest.mark.asyncio
async def test_subscribe_and_receive_published_message():
    broker = NotificationBroker()
    queue = await broker.subscribe()
    notif = _make_notification()

    await broker.publish(notif)

    received = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert received is notif


@pytest.mark.asyncio
async def test_multiple_subscribers_all_receive():
    broker = NotificationBroker()
    q1 = await broker.subscribe()
    q2 = await broker.subscribe()
    q3 = await broker.subscribe()

    notif = _make_notification("evt-multi")
    await broker.publish(notif)

    for q in (q1, q2, q3):
        received = await asyncio.wait_for(q.get(), timeout=1.0)
        assert received is notif


@pytest.mark.asyncio
async def test_unsubscribed_queue_does_not_receive():
    broker = NotificationBroker()
    q1 = await broker.subscribe()
    q2 = await broker.subscribe()

    await broker.unsubscribe(q1)
    await broker.publish(_make_notification())

    assert q1.empty()
    # q2 still subscribed
    assert not q2.empty()


@pytest.mark.asyncio
async def test_publish_does_not_block_when_one_queue_is_full():
    """慢消費者隊列滿載時，publish 仍應立即返回，不影響其他訂閱者。"""
    broker = NotificationBroker()
    slow_queue = await broker.subscribe()
    fast_queue = await broker.subscribe()

    # 把 slow_queue 灌滿至上限（64）
    for _ in range(64):
        slow_queue.put_nowait(_make_notification("filler"))

    # 此 publish 對 slow_queue 會 QueueFull → 應被吞掉，fast_queue 仍收到
    target = _make_notification("evt-target")
    await asyncio.wait_for(broker.publish(target), timeout=1.0)

    received = await asyncio.wait_for(fast_queue.get(), timeout=1.0)
    assert received is target


@pytest.mark.asyncio
async def test_subscriber_count_tracks_subscriptions():
    broker = NotificationBroker()
    assert await broker.subscriber_count() == 0

    q1 = await broker.subscribe()
    q2 = await broker.subscribe()
    assert await broker.subscriber_count() == 2

    await broker.unsubscribe(q1)
    assert await broker.subscriber_count() == 1

    await broker.unsubscribe(q2)
    assert await broker.subscriber_count() == 0


@pytest.mark.asyncio
async def test_publish_with_no_subscribers_is_noop():
    broker = NotificationBroker()
    # 不應拋出例外
    await broker.publish(_make_notification())


def test_notification_is_immutable():
    """frozen dataclass — 嘗試改欄位應拋 FrozenInstanceError。"""
    from dataclasses import FrozenInstanceError

    notif = _make_notification()
    with pytest.raises(FrozenInstanceError):
        notif.severity = 5  # type: ignore[misc]

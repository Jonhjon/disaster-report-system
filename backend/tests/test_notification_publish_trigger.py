"""驗證 chat.py 在新事件建立後會呼叫 broker.publish；合併路徑不會。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.llm_tools import SubmitDisasterReportPayload


def _new_event_tool_data(**overrides) -> SubmitDisasterReportPayload:
    data = {
        "disaster_type": "fire",
        "description": "新通報描述",
        "location_text": "台北市信義區松壽路1號",
        "severity": 3,
        "casualties": 0,
        "injured": 1,
        "trapped": 0,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "merge_event_id": "new",
        "reporter_name": "測試者",
        "reporter_phone": "0900000000",
    }
    data.update(overrides)
    return SubmitDisasterReportPayload.model_validate(data)


def _merge_tool_data(target_id) -> SubmitDisasterReportPayload:
    data = {
        "disaster_type": "fire",
        "description": "又有3人燒傷",
        "location_text": "台北市信義區松壽路1號",
        "severity": 3,
        "casualties": 0,
        "injured": 3,
        "trapped": 0,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "merge_event_id": str(target_id),
        "reporter_name": "測試者",
        "reporter_phone": "0900000000",
    }
    return SubmitDisasterReportPayload.model_validate(data)


def _make_existing_event():
    event = MagicMock()
    event.id = uuid.uuid4()
    event.title = "現有火警"
    event.disaster_type = "fire"
    event.description = "現有描述"
    event.location_text = "台北市信義區松壽路1號"
    event.severity = 3
    event.report_count = 1
    event.status = "reported"
    event.casualties = 0
    event.injured = 3
    event.severe_injured = 0
    event.trapped = 0
    event.occurred_at = datetime.now(timezone.utc)
    event.updated_at = datetime.now(timezone.utc)
    return event


def _coords():
    return {
        "latitude": 25.033,
        "longitude": 121.565,
        "display_name": "台北市信義區松壽路1號",
        "source": "google_places",
    }


@pytest.mark.asyncio
async def test_new_event_path_publishes_notification():
    """_create_new_event commit 後應呼叫 broker.publish。"""
    from app.api.chat import _process_tool_use

    mock_db = MagicMock()

    # mock event 在 db.add 後 flush 時取得 id（chat.py 用 event.id 序列化）
    captured_event = {}

    def capture_add(obj):
        # 模擬 flush 後 PK 被填入
        if not hasattr(obj, "_pk_assigned"):
            obj.id = uuid.uuid4()
            obj._pk_assigned = True
        captured_event.setdefault("event", obj)

    mock_db.add.side_effect = capture_add

    tool_data = _new_event_tool_data()

    mock_publish = AsyncMock()
    with patch("app.api.chat.get_broker") as mock_get_broker:
        mock_get_broker.return_value.publish = mock_publish
        result = await _process_tool_use(tool_data, "原始訊息", mock_db, _coords())

    assert result["status"] == "created"
    mock_publish.assert_awaited_once()

    # 驗證 publish 帶的 payload
    notif = mock_publish.await_args.args[0]
    assert notif.disaster_type == "fire"
    assert notif.severity == 3
    assert notif.location_text == "台北市信義區松壽路1號"
    assert notif.event_id == result["event_id"]


@pytest.mark.asyncio
async def test_merge_path_does_not_publish():
    """合併到既有事件不應呼叫 broker.publish。"""
    from app.api.chat import _process_tool_use

    target = _make_existing_event()
    mock_db = MagicMock()
    mock_query = mock_db.query.return_value
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = []
    mock_db.get.return_value = target

    tool_data = _merge_tool_data(target.id)

    mock_publish = AsyncMock()
    with (
        patch("app.api.chat.get_broker") as mock_get_broker,
        patch(
            "app.api.chat.merge_event_descriptions",
            new_callable=AsyncMock,
            return_value="合併描述",
        ),
        patch(
            "app.api.chat.reextract_numbers_from_description",
            new_callable=AsyncMock,
            return_value={"injured": 6},
        ),
    ):
        mock_get_broker.return_value.publish = mock_publish
        result = await _process_tool_use(tool_data, "原始訊息", mock_db, _coords())

    assert result["status"] == "merged"
    mock_publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_publish_failure_does_not_break_create():
    """broker.publish 拋例外時，新事件建立流程仍應成功完成。"""
    from app.api.chat import _process_tool_use

    mock_db = MagicMock()

    def capture_add(obj):
        if not hasattr(obj, "_pk_assigned"):
            obj.id = uuid.uuid4()
            obj._pk_assigned = True

    mock_db.add.side_effect = capture_add
    tool_data = _new_event_tool_data()

    failing_publish = AsyncMock(side_effect=RuntimeError("broker exploded"))
    with patch("app.api.chat.get_broker") as mock_get_broker:
        mock_get_broker.return_value.publish = failing_publish
        result = await _process_tool_use(tool_data, "原始訊息", mock_db, _coords())

    assert result["status"] == "created"
    failing_publish.assert_awaited_once()

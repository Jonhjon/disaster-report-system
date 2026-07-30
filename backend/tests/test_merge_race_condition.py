"""驗證 _merge_into_event 對 report_count / casualties / injured / trapped
使用 SQL-level atomic UPDATE，避免並發合併時的 lost update。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.sql.elements import BinaryExpression

from app.schemas.llm_tools import SubmitDisasterReportPayload


def _make_mock_event(**kwargs):
    event = MagicMock()
    event.id = kwargs.get("event_id") or uuid.uuid4()
    event.title = kwargs.get("title", "測試事件")
    event.disaster_type = kwargs.get("disaster_type", "fire")
    event.description = kwargs.get("description", "原描述")
    event.location_text = kwargs.get("location_text", "台北市信義區")
    event.severity = kwargs.get("severity", 2)
    event.report_count = kwargs.get("report_count", 1)
    event.status = kwargs.get("status", "reported")
    event.casualties = kwargs.get("casualties", 0)
    event.injured = kwargs.get("injured", 0)
    event.severe_injured = kwargs.get("severe_injured", 0)
    event.trapped = kwargs.get("trapped", 0)
    event.occurred_at = datetime.now(timezone.utc)
    event.updated_at = datetime.now(timezone.utc)
    return event


def _make_mock_db():
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.first.return_value = None
    return mock_db


def _tool_data(**overrides):
    data = {
        "disaster_type": "fire",
        "description": "新增描述",
        "location_text": "台北市信義區",
        "severity": 3,
        "casualties": 2,
        "injured": 1,
        "trapped": 0,
        "reporter_name": "測試者",
        "reporter_phone": "0900000000",
    }
    data.update(overrides)
    return SubmitDisasterReportPayload.model_validate(data)


@pytest.mark.asyncio
async def test_report_count_uses_sql_atomic_expression():
    """report_count 必須透過 SQL column expression (DisasterEvent.report_count + 1)
    更新，而非 Python target_event.report_count += 1。"""
    from app.api.chat import _merge_into_event
    from app.models.disaster_event import DisasterEvent

    event = _make_mock_event(report_count=5)
    db = _make_mock_db()

    with patch("app.api.chat.merge_event_descriptions", new=AsyncMock(return_value="合併後描述")), \
         patch("app.api.chat.reextract_numbers_from_description", new=AsyncMock(return_value={})):
        await _merge_into_event(
            target_event=event,
            tool_data=_tool_data(),
            raw_message="原始訊息",
            db=db,
            coords={"latitude": 25.0, "longitude": 121.5, "display_name": "addr"},
            occurred_at=datetime.now(timezone.utc),
            occurred_at_approximate=False,
        )

    # 驗證：report_count 被賦值為 SQL 表達式 (BinaryExpression)
    # 即 DisasterEvent.report_count + 1，這才有 atomic 語意
    # 注意：MagicMock 會儲存最後一次賦值
    assignments = [
        call for call in event.__setattr__.call_args_list
        if call[0][0] == "report_count"
    ] if hasattr(event.__setattr__, "call_args_list") else []

    # 直接檢查 event.report_count 目前狀態或 db.execute 被呼叫
    # 有兩種允許的實作：
    # 1. target_event.report_count = DisasterEvent.report_count + 1 (BinaryExpression)
    # 2. db.execute(update(...)) with atomic expression
    is_atomic_via_attr = isinstance(event.report_count, BinaryExpression)
    is_atomic_via_execute = db.execute.called
    assert is_atomic_via_attr or is_atomic_via_execute, (
        "report_count 必須使用 SQL atomic 更新；"
        f"目前 event.report_count 型別為 {type(event.report_count).__name__}、"
        f"db.execute called={db.execute.called}"
    )


@pytest.mark.asyncio
async def test_fallback_casualties_uses_sql_atomic_when_reextract_fails():
    """當 reextract 失敗進入 fallback 分支時，casualties/injured/trapped 必須
    透過 SQL atomic 更新避免 lost update。"""
    from app.api.chat import _merge_into_event
    from app.models.disaster_event import DisasterEvent

    event = _make_mock_event(casualties=10, injured=5, trapped=2)
    db = _make_mock_db()

    # reextract 丟例外 → 走 fallback 分支
    async def _raise(_):
        raise RuntimeError("LLM down")

    with patch("app.api.chat.merge_event_descriptions", new=AsyncMock(return_value="合併後描述")), \
         patch("app.api.chat.reextract_numbers_from_description", side_effect=_raise):
        await _merge_into_event(
            target_event=event,
            tool_data=_tool_data(casualties=3, injured=1, trapped=0),
            raw_message="原始",
            db=db,
            coords={"latitude": 25.0, "longitude": 121.5, "display_name": "addr"},
            occurred_at=datetime.now(timezone.utc),
            occurred_at_approximate=False,
        )

    is_atomic_via_attr = (
        isinstance(event.casualties, BinaryExpression)
        and isinstance(event.injured, BinaryExpression)
    )
    is_atomic_via_execute = db.execute.called
    assert is_atomic_via_attr or is_atomic_via_execute, (
        "fallback 分支 casualties/injured/trapped 必須使用 SQL atomic 更新"
    )


@pytest.mark.asyncio
async def test_extracted_branch_uses_absolute_set_not_atomic():
    """當 reextract 成功時，casualties 用 LLM 回傳的絕對值設定（非 atomic +=），
    維持原本語意。"""
    from app.api.chat import _merge_into_event

    event = _make_mock_event(casualties=0, injured=0, trapped=0)
    db = _make_mock_db()

    extracted_values = {"casualties": 7, "injured": 4, "trapped": 1, "severity": 4}

    with patch("app.api.chat.merge_event_descriptions", new=AsyncMock(return_value="合併後描述")), \
         patch("app.api.chat.reextract_numbers_from_description", new=AsyncMock(return_value=extracted_values)):
        await _merge_into_event(
            target_event=event,
            tool_data=_tool_data(),
            raw_message="原始",
            db=db,
            coords={"latitude": 25.0, "longitude": 121.5, "display_name": "addr"},
            occurred_at=datetime.now(timezone.utc),
            occurred_at_approximate=False,
        )

    # extracted 分支必須是絕對值設定
    assert event.casualties == 7
    assert event.injured == 4
    assert event.trapped == 1

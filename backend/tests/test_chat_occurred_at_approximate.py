"""_process_tool_use 對 occurred_at_approximate 的判定路徑。

三條路徑：
- LLM 給合法 ISO → approximate=False
- LLM 未給 → approximate=True，時間 fallback 為 now(UTC)
- LLM 給非法字串 → approximate=True，時間 fallback 為 now(UTC)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.llm_tools import SubmitDisasterReportPayload


def _base_tool_payload(**overrides) -> SubmitDisasterReportPayload:
    data = {
        "disaster_type": "fire",
        "description": "廚房失火",
        "location_text": "台北市信義區松仁路100號",
        "severity": 2,
        "casualties": 0,
        "injured": 0,
        "trapped": 0,
        "reporter_name": "測試",
        "reporter_phone": "0900000000",
    }
    data.update(overrides)
    return SubmitDisasterReportPayload.model_validate(data)


def _fake_create_returns_captured(captured: dict):
    """替代 _create_new_event，攔截傳入的 occurred_at_approximate 供斷言。"""

    async def _fake(*args, **kwargs):
        # 位置參數：tool_data, raw_message, db, coords, occurred_at, occurred_at_approximate
        captured["occurred_at"] = args[4]
        captured["occurred_at_approximate"] = args[5]
        return {"status": "created", "event_id": "fake"}

    return _fake


@pytest.mark.asyncio
async def test_llm_provides_valid_iso_marks_precise():
    from app.api.chat import _process_tool_use

    captured: dict = {}
    payload = _base_tool_payload(occurred_at="2026-07-15T09:30:00+08:00")

    with patch(
        "app.api.chat._create_new_event",
        new=_fake_create_returns_captured(captured),
    ), patch(
        "app.api.chat.find_and_score_candidates",
        new_callable=AsyncMock,
        return_value=[],
    ):
        await _process_tool_use(payload, "raw", MagicMock(), {"latitude": 25.0, "longitude": 121.5, "source": "google_places"})

    assert captured["occurred_at_approximate"] is False


@pytest.mark.asyncio
async def test_llm_omits_occurred_at_marks_approximate():
    from app.api.chat import _process_tool_use

    captured: dict = {}
    payload = _base_tool_payload()  # 未帶 occurred_at

    with patch(
        "app.api.chat._create_new_event",
        new=_fake_create_returns_captured(captured),
    ), patch(
        "app.api.chat.find_and_score_candidates",
        new_callable=AsyncMock,
        return_value=[],
    ):
        await _process_tool_use(payload, "raw", MagicMock(), {"latitude": 25.0, "longitude": 121.5, "source": "google_places"})

    assert captured["occurred_at_approximate"] is True


@pytest.mark.asyncio
async def test_llm_provides_invalid_iso_marks_approximate():
    from app.api.chat import _process_tool_use

    captured: dict = {}
    payload = _base_tool_payload(occurred_at="not-a-valid-iso-string")

    with patch(
        "app.api.chat._create_new_event",
        new=_fake_create_returns_captured(captured),
    ), patch(
        "app.api.chat.find_and_score_candidates",
        new_callable=AsyncMock,
        return_value=[],
    ):
        await _process_tool_use(payload, "raw", MagicMock(), {"latitude": 25.0, "longitude": 121.5, "source": "google_places"})

    assert captured["occurred_at_approximate"] is True

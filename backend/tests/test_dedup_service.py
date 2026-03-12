"""
方向三：去重複（Dedup）服務邏輯（4 案例）
策略：Mock DB 查詢 + Mock LLM 判斷
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.dedup_service import find_candidate_events, llm_judge_duplicate


def _make_mock_db():
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = []
    return mock_db


def _make_candidate():
    c = MagicMock()
    c.title = "台北地震"
    c.disaster_type = "earthquake"
    c.location_text = "台北市信義區"
    c.description = "芮氏規模5.0地震"
    c.occurred_at = datetime.now(timezone.utc)
    return c


# Case 11: earthquake 去重半徑應為 50,000 m
def test_find_candidate_events_earthquake_radius():
    mock_db = _make_mock_db()

    with patch("app.services.dedup_service.ST_DWithin") as mock_dwithin:
        mock_dwithin.return_value = MagicMock()

        find_candidate_events(
            mock_db,
            disaster_type="earthquake",
            latitude=25.0,
            longitude=121.5,
        )

        mock_dwithin.assert_called_once()
        radius_arg = mock_dwithin.call_args[0][2]
        assert radius_arg == 50_000


# Case 12: fire 去重半徑應為 5,000 m
def test_find_candidate_events_fire_radius():
    mock_db = _make_mock_db()

    with patch("app.services.dedup_service.ST_DWithin") as mock_dwithin:
        mock_dwithin.return_value = MagicMock()

        find_candidate_events(
            mock_db,
            disaster_type="fire",
            latitude=25.0,
            longitude=121.5,
        )

        mock_dwithin.assert_called_once()
        radius_arg = mock_dwithin.call_args[0][2]
        assert radius_arg == 5_000


# Case 13: LLM 回傳 "YES" → True（視為重複事件）
@pytest.mark.asyncio
async def test_llm_judge_duplicate_yes():
    candidate = _make_candidate()

    with patch("app.services.dedup_service.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="YES")]
        mock_client.messages.create = AsyncMock(return_value=mock_message)

        result = await llm_judge_duplicate("台北市發生規模5地震", candidate)

    assert result is True


# Case 14: LLM 回傳 "NO" → False（視為新事件）
@pytest.mark.asyncio
async def test_llm_judge_duplicate_no():
    candidate = _make_candidate()

    with patch("app.services.dedup_service.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="NO")]
        mock_client.messages.create = AsyncMock(return_value=mock_message)

        result = await llm_judge_duplicate("台北市信義區火災", candidate)

    assert result is False

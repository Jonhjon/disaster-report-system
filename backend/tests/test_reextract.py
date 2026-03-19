"""測試 reextract_numbers_from_description() 及合併分支的重新萃取邏輯"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.llm_service import reextract_numbers_from_description


# ── reextract_numbers_from_description 單元測試 ──────────────────────────────

@pytest.mark.asyncio
async def test_reextract_returns_correct_numbers():
    """LLM 正確回傳 JSON → 欄位正確萃取"""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"casualties":0,"injured":6,"trapped":2,"severity":3}')]

    with patch("app.services.llm_service._get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get.return_value = mock_client

        result = await reextract_numbers_from_description("火災造成6人受傷，2人受困")

    assert result["injured"] == 6
    assert result["trapped"] == 2
    assert result["severity"] == 3
    assert result["casualties"] == 0  # 0 也應回傳（呼叫端再判斷要不要採用）


@pytest.mark.asyncio
async def test_reextract_handles_markdown_code_fence():
    """LLM 輸出包含 markdown code fence → 防禦性清理後仍能解析"""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(
        text='```json\n{"casualties":null,"injured":3,"trapped":null,"severity":4}\n```'
    )]

    with patch("app.services.llm_service._get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get.return_value = mock_client

        result = await reextract_numbers_from_description("3人受傷")

    assert result["injured"] == 3
    assert result["severity"] == 4
    assert "casualties" not in result   # null → 不放入 result
    assert "trapped" not in result


@pytest.mark.asyncio
async def test_reextract_returns_empty_dict_on_llm_failure():
    """LLM 拋出例外 → 回傳 {} （呼叫端保留 max() 值）"""
    with patch("app.services.llm_service._get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("API error"))
        mock_get.return_value = mock_client

        result = await reextract_numbers_from_description("火災現場混亂")

    assert result == {}


@pytest.mark.asyncio
async def test_reextract_short_circuits_on_empty_description():
    """空描述 → 直接回傳 {}，不呼叫 LLM"""
    with patch("app.services.llm_service._get_client") as mock_get:
        result = await reextract_numbers_from_description("")

    mock_get.assert_not_called()
    assert result == {}


@pytest.mark.asyncio
async def test_reextract_ignores_invalid_severity():
    """severity 超出 1-5 範圍 → 不放入 result"""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(
        text='{"casualties":null,"injured":2,"trapped":null,"severity":7}'
    )]

    with patch("app.services.llm_service._get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get.return_value = mock_client

        result = await reextract_numbers_from_description("2人受傷")

    assert result["injured"] == 2
    assert "severity" not in result   # 7 超出範圍，不採用


# ── _process_tool_use 合併分支整合測試 ────────────────────────────────────────

@pytest.mark.asyncio
async def test_merge_branch_updates_fields_from_reextract(mock_db):
    """描述發生變化 → reextract 被呼叫，injured 更新為描述中的值"""
    from unittest.mock import patch, AsyncMock, MagicMock
    from app.api.chat import _process_tool_use

    mock_event = MagicMock()
    mock_event.id = __import__("uuid").uuid4()
    mock_event.title = "中山路火災"
    mock_event.report_count = 1
    mock_event.severity = 3
    mock_event.casualties = 0
    mock_event.injured = 5
    mock_event.trapped = 0
    mock_event.description = "中山路7-11發生火災，5人受傷。"

    tool_data = {
        "disaster_type": "fire",
        "description": "中山路便利商店火災，確認6人受傷，均已送醫。",
        "location_text": "台北市中山路",
        "severity": 3,
        "latitude": 25.05,
        "longitude": 121.53,
        "casualties": 0,
        "injured": 6,
        "trapped": 0,
    }

    with (
        patch("app.api.chat.geocode_address", new_callable=AsyncMock,
              return_value={"display_name": "台北市中山路", "latitude": 25.05, "longitude": 121.53}),
        patch("app.api.chat.find_candidate_events", return_value=[mock_event]),
        patch("app.api.chat.is_duplicate", new_callable=AsyncMock, return_value=True),
        patch("app.api.chat.merge_event_descriptions", new_callable=AsyncMock,
              return_value="中山路7-11發生火災，確認6人受傷均已送醫。"),
        patch("app.api.chat.reextract_numbers_from_description", new_callable=AsyncMock,
              return_value={"casualties": 0, "injured": 6, "trapped": 0, "severity": 3}) as mock_reextract,
    ):
        result = await _process_tool_use(tool_data, "通報訊息", mock_db)

    assert result["status"] == "merged"
    assert mock_event.injured == 6      # 從 5 更新為 6
    mock_reextract.assert_called_once()


@pytest.mark.asyncio
async def test_merge_branch_skips_reextract_when_description_unchanged(mock_db):
    """描述未變化（短路情況）→ reextract 不被呼叫"""
    from app.api.chat import _process_tool_use

    same_desc = "中山路7-11發生火災，5人受傷。"
    mock_event = MagicMock()
    mock_event.id = __import__("uuid").uuid4()
    mock_event.title = "中山路火災"
    mock_event.report_count = 1
    mock_event.severity = 3
    mock_event.casualties = 0
    mock_event.injured = 5
    mock_event.trapped = 0
    mock_event.description = same_desc

    tool_data = {
        "disaster_type": "fire",
        "description": same_desc,
        "location_text": "台北市中山路",
        "severity": 3,
        "latitude": 25.05,
        "longitude": 121.53,
        "casualties": 0,
        "injured": 5,
        "trapped": 0,
    }

    with (
        patch("app.api.chat.geocode_address", new_callable=AsyncMock,
              return_value={"display_name": "台北市中山路", "latitude": 25.05, "longitude": 121.53}),
        patch("app.api.chat.find_candidate_events", return_value=[mock_event]),
        patch("app.api.chat.is_duplicate", new_callable=AsyncMock, return_value=True),
        patch("app.api.chat.merge_event_descriptions", new_callable=AsyncMock,
              return_value=same_desc),   # 描述未變化（短路）
        patch("app.api.chat.reextract_numbers_from_description", new_callable=AsyncMock) as mock_reextract,
    ):
        await _process_tool_use(tool_data, "通報訊息", mock_db)

    mock_reextract.assert_not_called()  # 短路情況不呼叫

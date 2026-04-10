"""
去重合併流程觸發測試（Dedup Flow in SSE endpoint）

測試情境模擬使用者描述的真實場景：
  第一筆通報：花蓮縣餅火警 → 建立事件 A
  第二筆通報：同地點、同類型 → 應觸發去重，顯示候選卡片

測試兩個 Bug 的修復：

Bug 1 — 地址消歧義（disambiguation）後去重未觸發：
  geocoding 返回多個分店 → 消歧義流程觸發 → 使用者選定後再次提交
  → _process_tool_use 找到候選 → 應發出 candidates_selection SSE 事件
  → Bug：直接發 report_submitted，candidates_selection 從未出現

Bug 2 — 地址精確度追問（precision clarification）後去重未觸發：
  geocoding 精確度不足 → 追問流程觸發 → 使用者提供具體地址後再次提交
  → _process_tool_use 找到候選 → 應發出 candidates_selection SSE 事件
  → Bug：直接發 report_submitted，candidates_selection 從未出現
"""

import json
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def parse_sse_events(body: str) -> list[dict]:
    """從 SSE 回應 body 解析出所有 data 事件。"""
    events = []
    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            try:
                data = json.loads(line[6:])
                events.append(data)
            except json.JSONDecodeError:
                pass
    return events


def _make_existing_fire_event():
    """建立模擬的「第一筆通報」已存在事件（DB 中已有的火警）。"""
    event = MagicMock()
    event.id = uuid4()
    event.title = "花蓮縣餅前站火警"
    event.disaster_type = "fire"
    event.description = "花蓮縣餅發生火災，火勢蔓延，3人燒傷"
    event.location_text = "花蓮火車站前站的花蓮縣餅"
    event.severity = 3
    event.report_count = 1
    event.status = "reported"
    event.casualties = 0
    event.injured = 3
    event.trapped = 0
    event.occurred_at = datetime.now(timezone.utc)
    event.updated_at = datetime.now(timezone.utc)
    return event


def _dedup_candidates_for(event):
    """為指定事件建立去重候選清單（高相似度）。"""
    return [{
        "event": event,
        "score": 0.85,
        "distance_m": 30,
    }]


def _make_fire_tool_data(location_text: str = "花蓮縣餅") -> dict:
    return {
        "disaster_type": "fire",
        "description": "花蓮縣餅又有三人燒傷，火勢持續",
        "location_text": location_text,
        "severity": 3,
        "casualties": 0,
        "injured": 3,
        "trapped": 0,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }


def _precise_coords(location_name: str = "花蓮縣餅前站") -> dict:
    return {
        "latitude": 23.9882,
        "longitude": 121.6016,
        "display_name": location_name,
        "source": "google_places",
    }


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def client(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


# ═══════════════════════════════════════════════════════════════════════════════
# Bug 1：地址消歧義後去重未觸發
# ═══════════════════════════════════════════════════════════════════════════════

class TestDedupAfterGeocodeDisambiguation:
    """
    情境：geocoding 返回多個候選地點 → 消歧義流程 → 使用者選定地點 →
          再次提交時去重找到第一筆事件 → 應顯示 candidates_selection 卡片
    """

    def test_candidates_selection_emitted_after_geocode_disambiguation(self, client):
        """
        核心測試：消歧義 continuation 內發現去重候選時，
        應發出 candidates_selection SSE 事件（而非直接 report_submitted）。
        """
        existing_event = _make_existing_fire_event()
        dedup_candidates = _dedup_candidates_for(existing_event)

        # 第一次呼叫 stream_chat：回傳有曖昧地址的 tool_use
        first_tool_data = _make_fire_tool_data("花蓮縣餅")
        # 第二次呼叫 stream_chat（消歧義 continuation）：回傳具體地點的 tool_use
        second_tool_data = _make_fire_tool_data("花蓮縣餅前站")

        stream_call_count = [0]

        async def mock_stream_chat(messages):
            stream_call_count[0] += 1
            if stream_call_count[0] == 1:
                yield {"type": "text", "content": "請確認是哪個分店"}
                yield {
                    "type": "tool_use",
                    "tool": "submit_disaster_report",
                    "data": first_tool_data,
                    "tool_use_id": "tool_id_1",
                }
                yield {"type": "done"}
            else:
                # 消歧義 continuation：使用者選了前站
                yield {"type": "text", "content": "好的，已選前站"}
                yield {
                    "type": "tool_use",
                    "tool": "submit_disaster_report",
                    "data": second_tool_data,
                    "tool_use_id": "tool_id_2",
                }
                yield {"type": "done"}

        geocode_call_count = [0]

        async def mock_geocode(location):
            geocode_call_count[0] += 1
            if geocode_call_count[0] == 1:
                # 第一次：返回多個候選地點 → 觸發消歧義
                return {
                    "latitude": 23.9882,
                    "longitude": 121.6016,
                    "display_name": "花蓮縣餅",
                    "source": "google_places",
                    "candidates": [
                        {
                            "name": "花蓮縣餅前站",
                            "address": "花蓮市中山路57號",
                            "latitude": 23.9882,
                            "longitude": 121.6016,
                            "distance_m": 0,
                        },
                        {
                            "name": "花蓮縣餅後站",
                            "address": "花蓮市國聯一路X號",
                            "latitude": 23.9850,
                            "longitude": 121.6010,
                            "distance_m": 350,
                        },
                    ],
                }
            else:
                # 第二次：使用者選定後的精確座標
                return _precise_coords("花蓮縣餅前站")

        with (
            patch("app.api.chat.llm_service.stream_chat", side_effect=mock_stream_chat),
            patch("app.api.chat.geocode_address", side_effect=mock_geocode),
            patch(
                "app.api.chat.find_and_score_candidates",
                new_callable=AsyncMock,
                return_value=dedup_candidates,
            ),
        ):
            response = client.post(
                "/api/chat",
                json={
                    "message": "花蓮火車站前站的花蓮縣餅又有三人燒傷了",
                    "history": [],
                },
            )

        assert response.status_code == 200

        events = parse_sse_events(response.text)
        event_types = [e.get("type") for e in events]

        assert "candidates_selection" in event_types, (
            f"Bug 1：消歧義後去重未觸發。實際收到的事件類型：{event_types}\n"
            f"完整 SSE 回應：{response.text[:500]}"
        )

    def test_no_candidates_selection_when_no_dedup_match(self, client):
        """消歧義後 DB 無相符事件時，應直接建立新事件（正常流程）。"""
        first_tool_data = _make_fire_tool_data("花蓮縣餅")
        second_tool_data = _make_fire_tool_data("花蓮縣餅前站")

        stream_call_count = [0]

        async def mock_stream_chat(messages):
            stream_call_count[0] += 1
            if stream_call_count[0] == 1:
                yield {"type": "tool_use", "tool": "submit_disaster_report",
                       "data": first_tool_data, "tool_use_id": "id_1"}
                yield {"type": "done"}
            else:
                yield {"type": "tool_use", "tool": "submit_disaster_report",
                       "data": second_tool_data, "tool_use_id": "id_2"}
                yield {"type": "done"}

        geocode_call_count = [0]

        async def mock_geocode(location):
            geocode_call_count[0] += 1
            if geocode_call_count[0] == 1:
                return {
                    "latitude": 23.9882, "longitude": 121.6016,
                    "display_name": "花蓮縣餅", "source": "google_places",
                    "candidates": [
                        {"name": "前站", "address": "A路", "latitude": 23.9882, "longitude": 121.6016, "distance_m": 0},
                        {"name": "後站", "address": "B路", "latitude": 23.985, "longitude": 121.601, "distance_m": 300},
                    ],
                }
            else:
                return _precise_coords()

        with (
            patch("app.api.chat.llm_service.stream_chat", side_effect=mock_stream_chat),
            patch("app.api.chat.geocode_address", side_effect=mock_geocode),
            patch(
                "app.api.chat.find_and_score_candidates",
                new_callable=AsyncMock,
                return_value=[],   # 無候選
            ),
        ):
            mock_db = MagicMock()
            app.dependency_overrides[get_db] = lambda: mock_db
            response = client.post(
                "/api/chat",
                json={"message": "花蓮縣餅火警", "history": []},
            )

        events = parse_sse_events(response.text)
        event_types = [e.get("type") for e in events]

        assert "candidates_selection" not in event_types
        assert "report_submitted" in event_types


# ═══════════════════════════════════════════════════════════════════════════════
# Bug 2：地址精確度追問後去重未觸發
# ═══════════════════════════════════════════════════════════════════════════════

class TestDedupAfterPrecisionClarification:
    """
    情境：geocoding 精確度不足（無門牌、無路名）→ 系統追問使用者 →
          使用者提供具體地址後再次提交 →
          去重找到第一筆事件 → 應顯示 candidates_selection 卡片
    """

    def test_candidates_selection_emitted_after_precision_clarification(self, client):
        """
        核心測試：精確度追問 continuation 內發現去重候選時，
        應發出 candidates_selection SSE 事件（而非直接 report_submitted）。
        """
        existing_event = _make_existing_fire_event()
        dedup_candidates = _dedup_candidates_for(existing_event)

        imprecise_tool_data = _make_fire_tool_data("花蓮縣餅")
        precise_tool_data = _make_fire_tool_data("花蓮市中山路57號花蓮縣餅前站")

        stream_call_count = [0]

        async def mock_stream_chat(messages):
            stream_call_count[0] += 1
            if stream_call_count[0] == 1:
                yield {"type": "text", "content": "請提供更精確的地址"}
                yield {
                    "type": "tool_use",
                    "tool": "submit_disaster_report",
                    "data": imprecise_tool_data,
                    "tool_use_id": "tool_id_1",
                }
                yield {"type": "done"}
            else:
                # 精確度追問 continuation
                yield {"type": "text", "content": "收到地址，重新提交"}
                yield {
                    "type": "tool_use",
                    "tool": "submit_disaster_report",
                    "data": precise_tool_data,
                    "tool_use_id": "tool_id_2",
                }
                yield {"type": "done"}

        geocode_call_count = [0]

        async def mock_geocode(location):
            geocode_call_count[0] += 1
            if geocode_call_count[0] == 1:
                # 第一次：精確度不足（無路名、無門牌，source 非 google_places）
                return {
                    "latitude": 23.9882,
                    "longitude": 121.6016,
                    "display_name": "花蓮縣餅",
                    "source": "nominatim",  # 非 google_places → location_precise 可能為 False
                }
            else:
                # 第二次：精確地址
                return _precise_coords("花蓮市中山路57號花蓮縣餅前站")

        with (
            patch("app.api.chat.llm_service.stream_chat", side_effect=mock_stream_chat),
            patch("app.api.chat.geocode_address", side_effect=mock_geocode),
            patch("app.api.chat._location_is_precise", side_effect=[False, True]),
            patch(
                "app.api.chat.find_and_score_candidates",
                new_callable=AsyncMock,
                return_value=dedup_candidates,
            ),
        ):
            response = client.post(
                "/api/chat",
                json={
                    "message": "花蓮縣餅又有三人燒傷了",
                    "history": [],
                },
            )

        assert response.status_code == 200

        events = parse_sse_events(response.text)
        event_types = [e.get("type") for e in events]

        assert "candidates_selection" in event_types, (
            f"Bug 2：精確度追問後去重未觸發。實際收到的事件類型：{event_types}\n"
            f"完整 SSE 回應：{response.text[:500]}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 正常路徑：直接 geocoding 成功 + 去重觸發（基準測試，應已通過）
# ═══════════════════════════════════════════════════════════════════════════════

class TestDedupHappyPath:
    """
    基準情境：geocoding 直接返回單一精確結果（無消歧義、無追問），
    去重正常觸發。此測試應在修復前後都通過。
    """

    def test_candidates_selection_shown_on_direct_dedup_match(self, client):
        """geocoding 成功、無需消歧義時，去重應正常觸發。"""
        existing_event = _make_existing_fire_event()
        dedup_candidates = _dedup_candidates_for(existing_event)
        tool_data = _make_fire_tool_data("花蓮市中山路57號花蓮縣餅前站")

        async def mock_stream_chat(messages):
            yield {"type": "text", "content": "確認地址"}
            yield {
                "type": "tool_use",
                "tool": "submit_disaster_report",
                "data": tool_data,
                "tool_use_id": "tool_id_1",
            }
            yield {"type": "done"}

        with (
            patch("app.api.chat.llm_service.stream_chat", side_effect=mock_stream_chat),
            patch(
                "app.api.chat.geocode_address",
                new_callable=AsyncMock,
                return_value=_precise_coords("花蓮市中山路57號花蓮縣餅前站"),
            ),
            patch(
                "app.api.chat.find_and_score_candidates",
                new_callable=AsyncMock,
                return_value=dedup_candidates,
            ),
        ):
            response = client.post(
                "/api/chat",
                json={
                    "message": "花蓮縣餅又有三人燒傷了",
                    "history": [],
                },
            )

        assert response.status_code == 200

        events = parse_sse_events(response.text)
        event_types = [e.get("type") for e in events]

        assert "candidates_selection" in event_types, (
            f"正常路徑去重未觸發（非預期）。收到的事件類型：{event_types}"
        )

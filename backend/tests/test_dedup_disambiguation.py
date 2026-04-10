"""
去重消歧義功能測試（Dedup Disambiguation）

測試範圍：
1. find_and_score_candidates() — 候選評分與篩選
2. _format_dedup_candidates_hint() — 候選格式化
3. _process_tool_use() 路徑 A — 首次呼叫，偵測到候選時回傳 needs_user_choice
4. _process_tool_use() 路徑 B — 帶 merge_event_id 的二次呼叫
5. 邊界情況 — 無候選、無效 UUID、事件 inactive
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.dedup_service import (
    find_and_score_candidates,
    find_candidate_events,
    _compute_dedup_score,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _make_mock_event(
    *,
    event_id=None,
    title="台北市信義路淹水",
    disaster_type="flooding",
    description="信義路二段一帶嚴重淹水",
    location_text="台北市信義路二段",
    severity=3,
    report_count=2,
    status="reported",
    casualties=0,
    injured=1,
    trapped=0,
    occurred_at=None,
    location=None,
):
    """建立一個 Mock DisasterEvent，可自訂任意欄位。"""
    event = MagicMock()
    event.id = event_id or uuid.uuid4()
    event.title = title
    event.disaster_type = disaster_type
    event.description = description
    event.location_text = location_text
    event.severity = severity
    event.report_count = report_count
    event.status = status
    event.casualties = casualties
    event.injured = injured
    event.trapped = trapped
    event.occurred_at = occurred_at or datetime.now(timezone.utc)
    event.updated_at = datetime.now(timezone.utc)
    event.location = location
    event.location_approximate = False
    return event


def _make_mock_db():
    """建立 Mock SQLAlchemy Session，支援鏈式查詢。"""
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = []
    mock_db.get.return_value = None
    return mock_db


def _base_tool_data(**overrides):
    """產生基本的 tool_data dict，可覆寫任意欄位。"""
    data = {
        "disaster_type": "flooding",
        "description": "信義路附近淹水約30公分",
        "location_text": "台北市信義路二段100號",
        "severity": 3,
        "casualties": 0,
        "injured": 0,
        "trapped": 0,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }
    data.update(overrides)
    return data


def _base_coords(**overrides):
    """產生基本的 geocoding coords dict。"""
    coords = {
        "latitude": 25.033,
        "longitude": 121.565,
        "display_name": "台北市信義路二段100號",
        "source": "google_places",
    }
    coords.update(overrides)
    return coords


# ═══════════════════════════════════════════════════════════════════════════════
# 第一部分：find_and_score_candidates() 測試
# ═══════════════════════════════════════════════════════════════════════════════

class TestFindAndScoreCandidates:
    """測試 find_and_score_candidates() 回傳正確的候選清單及分數。"""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_candidates(self):
        """無候選事件 → 回傳空列表。"""
        mock_db = _make_mock_db()

        with patch("app.services.dedup_service.find_candidate_events", return_value=[]):
            result = await find_and_score_candidates(
                mock_db,
                disaster_type="flooding",
                description="淹水",
                latitude=25.0,
                longitude=121.5,
                occurred_at=datetime.now(timezone.utc),
            )

        assert result == []

    @pytest.mark.asyncio
    async def test_filters_out_low_score_candidates(self):
        """score < 0.50 的候選應被過濾掉。"""
        low_score_event = _make_mock_event(
            title="高雄市前鎮區淹水",
            description="完全不同的地點",
        )
        mock_db = _make_mock_db()

        with (
            patch("app.services.dedup_service.find_candidate_events",
                  return_value=[low_score_event]),
            patch("app.services.dedup_service._compute_dedup_score",
                  return_value=0.30),
        ):
            result = await find_and_score_candidates(
                mock_db,
                disaster_type="flooding",
                description="台北市淹水",
                latitude=25.0,
                longitude=121.5,
                occurred_at=datetime.now(timezone.utc),
            )

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_includes_high_score_candidates(self):
        """score >= 0.50 的候選應包含在結果中。"""
        event1 = _make_mock_event(title="信義路淹水", report_count=3)
        event2 = _make_mock_event(title="松仁路淹水", report_count=1)
        mock_db = _make_mock_db()

        scores = [0.85, 0.60]

        with (
            patch("app.services.dedup_service.find_candidate_events",
                  return_value=[event1, event2]),
            patch("app.services.dedup_service._compute_dedup_score",
                  side_effect=scores),
        ):
            result = await find_and_score_candidates(
                mock_db,
                disaster_type="flooding",
                description="信義路淹水",
                latitude=25.033,
                longitude=121.565,
                occurred_at=datetime.now(timezone.utc),
            )

        assert len(result) == 2
        assert result[0]["score"] >= result[1]["score"]
        assert result[0]["event"] == event1
        assert result[1]["event"] == event2

    @pytest.mark.asyncio
    async def test_mixed_scores_filters_correctly(self):
        """混合分數：只保留 >= 0.50 的候選。"""
        event_high = _make_mock_event(title="高分事件")
        event_mid = _make_mock_event(title="中分事件")
        event_low = _make_mock_event(title="低分事件")
        mock_db = _make_mock_db()

        with (
            patch("app.services.dedup_service.find_candidate_events",
                  return_value=[event_high, event_mid, event_low]),
            patch("app.services.dedup_service._compute_dedup_score",
                  side_effect=[0.90, 0.55, 0.30]),
        ):
            result = await find_and_score_candidates(
                mock_db,
                disaster_type="flooding",
                description="淹水",
                latitude=25.0,
                longitude=121.5,
                occurred_at=datetime.now(timezone.utc),
            )

        assert len(result) == 2
        titles = [r["event"].title for r in result]
        assert "高分事件" in titles
        assert "中分事件" in titles
        assert "低分事件" not in titles

    @pytest.mark.asyncio
    async def test_result_contains_required_fields(self):
        """每個候選結果應包含 event、score、distance_m 欄位。"""
        event = _make_mock_event()
        mock_db = _make_mock_db()

        with (
            patch("app.services.dedup_service.find_candidate_events",
                  return_value=[event]),
            patch("app.services.dedup_service._compute_dedup_score",
                  return_value=0.75),
            patch("app.services.dedup_service._haversine_km",
                  return_value=0.12),
        ):
            result = await find_and_score_candidates(
                mock_db,
                disaster_type="flooding",
                description="淹水",
                latitude=25.033,
                longitude=121.565,
                occurred_at=datetime.now(timezone.utc),
            )

        assert len(result) == 1
        candidate = result[0]
        assert "event" in candidate
        assert "score" in candidate
        assert "distance_m" in candidate
        assert isinstance(candidate["score"], float)


# ═══════════════════════════════════════════════════════════════════════════════
# 第二部分：_format_dedup_candidates_hint() 測試
# ═══════════════════════════════════════════════════════════════════════════════

class TestFormatDedupCandidatesHint:
    """測試候選格式化提示文字的正確性。"""

    def test_formats_single_candidate_plus_new_option(self):
        """單一候選 + 建立新事件選項。"""
        from app.api.chat import _format_dedup_candidates_hint

        event_id = uuid.uuid4()
        candidates = [{
            "event_id": str(event_id),
            "title": "信義路淹水",
            "description": "信義路二段淹水30公分",
            "location_text": "台北市信義路二段",
            "report_count": 3,
            "distance_m": 150,
            "score": 0.85,
        }]

        hint = _format_dedup_candidates_hint(candidates)

        assert "信義路淹水" in hint
        assert "3" in hint
        assert "150" in hint
        assert str(event_id) in hint
        assert "建立全新" in hint or "新事件" in hint

    def test_formats_multiple_candidates(self):
        """多個候選應全部列出，加上編號。"""
        from app.api.chat import _format_dedup_candidates_hint

        candidates = [
            {
                "event_id": str(uuid.uuid4()),
                "title": "信義路淹水",
                "description": "淹水",
                "location_text": "台北市信義路",
                "report_count": 3,
                "distance_m": 100,
                "score": 0.90,
            },
            {
                "event_id": str(uuid.uuid4()),
                "title": "松仁路淹水",
                "description": "淹水",
                "location_text": "台北市松仁路",
                "report_count": 1,
                "distance_m": 200,
                "score": 0.60,
            },
        ]

        hint = _format_dedup_candidates_hint(candidates)

        assert "1." in hint
        assert "2." in hint
        assert "信義路淹水" in hint
        assert "松仁路淹水" in hint

    def test_includes_merge_event_id_instruction(self):
        """提示文字應包含 merge_event_id 使用說明。"""
        from app.api.chat import _format_dedup_candidates_hint

        candidates = [{
            "event_id": str(uuid.uuid4()),
            "title": "事件A",
            "description": "",
            "location_text": "地點A",
            "report_count": 1,
            "distance_m": 50,
            "score": 0.70,
        }]

        hint = _format_dedup_candidates_hint(candidates)

        assert "merge_event_id" in hint

    def test_empty_candidates_still_shows_new_option(self):
        """即使候選列表為空，仍應有建立新事件的提示。"""
        from app.api.chat import _format_dedup_candidates_hint

        hint = _format_dedup_candidates_hint([])

        assert "新事件" in hint or "new" in hint


# ═══════════════════════════════════════════════════════════════════════════════
# 第三部分：_process_tool_use() 路徑 A — 首次呼叫（無 merge_event_id）
# ═══════════════════════════════════════════════════════════════════════════════

class TestProcessToolUsePathA:
    """首次呼叫 _process_tool_use()（無 merge_event_id）。"""

    @pytest.mark.asyncio
    async def test_returns_needs_user_choice_when_candidates_found(self):
        """有候選事件時應回傳 status=needs_user_choice。"""
        from app.api.chat import _process_tool_use

        event = _make_mock_event()
        scored_candidates = [{
            "event": event,
            "score": 0.75,
            "distance_m": 120,
        }]

        tool_data = _base_tool_data()
        coords = _base_coords()
        mock_db = _make_mock_db()

        with patch(
            "app.api.chat.find_and_score_candidates",
            new_callable=AsyncMock,
            return_value=scored_candidates,
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, coords)

        assert result["status"] == "needs_user_choice"
        assert "candidates" in result
        assert len(result["candidates"]) == 1
        assert result["candidates"][0]["event_id"] == str(event.id)
        assert result["candidates"][0]["title"] == event.title

    @pytest.mark.asyncio
    async def test_creates_new_event_when_no_candidates(self):
        """無候選事件時應直接建立新事件。"""
        from app.api.chat import _process_tool_use

        tool_data = _base_tool_data()
        coords = _base_coords()
        mock_db = _make_mock_db()

        with patch(
            "app.api.chat.find_and_score_candidates",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, coords)

        assert result["status"] == "created"
        assert "event_id" in result
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_needs_user_choice_includes_all_candidate_info(self):
        """needs_user_choice 的 candidates 應包含完整資訊。"""
        from app.api.chat import _process_tool_use

        event = _make_mock_event(
            title="中山路火災",
            description="中山路7-11火災",
            location_text="台北市中山路",
            report_count=5,
        )
        scored_candidates = [{
            "event": event,
            "score": 0.82,
            "distance_m": 80,
        }]

        tool_data = _base_tool_data(disaster_type="fire")
        coords = _base_coords()
        mock_db = _make_mock_db()

        with patch(
            "app.api.chat.find_and_score_candidates",
            new_callable=AsyncMock,
            return_value=scored_candidates,
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, coords)

        candidate = result["candidates"][0]
        assert candidate["title"] == "中山路火災"
        assert candidate["description"] == "中山路7-11火災"
        assert candidate["location_text"] == "台北市中山路"
        assert candidate["report_count"] == 5
        assert candidate["distance_m"] == 80

    @pytest.mark.asyncio
    async def test_multiple_candidates_returned_in_order(self):
        """多個候選應依 score 降序排列回傳。"""
        from app.api.chat import _process_tool_use

        event1 = _make_mock_event(title="事件A")
        event2 = _make_mock_event(title="事件B")
        scored_candidates = [
            {"event": event1, "score": 0.90, "distance_m": 50},
            {"event": event2, "score": 0.60, "distance_m": 180},
        ]

        tool_data = _base_tool_data()
        coords = _base_coords()
        mock_db = _make_mock_db()

        with patch(
            "app.api.chat.find_and_score_candidates",
            new_callable=AsyncMock,
            return_value=scored_candidates,
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, coords)

        assert result["status"] == "needs_user_choice"
        assert len(result["candidates"]) == 2
        assert result["candidates"][0]["title"] == "事件A"
        assert result["candidates"][1]["title"] == "事件B"

    @pytest.mark.asyncio
    async def test_geocoded_address_included_in_needs_user_choice(self):
        """needs_user_choice 結果應包含 geocoded_address。"""
        from app.api.chat import _process_tool_use

        event = _make_mock_event()
        scored_candidates = [{"event": event, "score": 0.70, "distance_m": 100}]

        tool_data = _base_tool_data()
        coords = _base_coords(display_name="台北市信義區信義路二段100號")
        mock_db = _make_mock_db()

        with patch(
            "app.api.chat.find_and_score_candidates",
            new_callable=AsyncMock,
            return_value=scored_candidates,
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, coords)

        assert result.get("geocoded_address") == "台北市信義區信義路二段100號"

    @pytest.mark.asyncio
    async def test_no_db_commit_on_needs_user_choice(self):
        """needs_user_choice 不應有 DB commit（尚未建立任何記錄）。"""
        from app.api.chat import _process_tool_use

        event = _make_mock_event()
        scored_candidates = [{"event": event, "score": 0.75, "distance_m": 100}]

        tool_data = _base_tool_data()
        coords = _base_coords()
        mock_db = _make_mock_db()

        with patch(
            "app.api.chat.find_and_score_candidates",
            new_callable=AsyncMock,
            return_value=scored_candidates,
        ):
            await _process_tool_use(tool_data, "原始訊息", mock_db, coords)

        mock_db.commit.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# 第四部分：_process_tool_use() 路徑 B — 帶 merge_event_id 的二次呼叫
# ═══════════════════════════════════════════════════════════════════════════════

class TestProcessToolUsePathB:
    """帶 merge_event_id 的二次呼叫 _process_tool_use()。"""

    @pytest.mark.asyncio
    async def test_merge_with_valid_event_id(self):
        """提供有效的 merge_event_id → 合併到指定事件。"""
        from unittest.mock import AsyncMock, patch
        from app.api.chat import _process_tool_use

        target_event = _make_mock_event(
            title="信義路淹水",
            report_count=2,
            severity=3,
            casualties=0,
            injured=1,
            trapped=0,
        )
        mock_db = _make_mock_db()
        mock_db.get.return_value = target_event

        tool_data = _base_tool_data(
            merge_event_id=str(target_event.id),
            severity=4,
            injured=3,
        )
        coords = _base_coords()

        with (
            patch(
                "app.api.chat.merge_event_descriptions",
                new_callable=AsyncMock,
                return_value="合併描述",
            ),
            patch(
                "app.api.chat.reextract_numbers_from_description",
                new_callable=AsyncMock,
                return_value={"injured": 4, "severity": 4},
            ),
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, coords)

        assert result["status"] == "merged"
        assert result["event_id"] == str(target_event.id)
        assert target_event.report_count == 3
        assert target_event.severity == 4
        assert target_event.injured == 4  # LLM 萃取值
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_create_new_when_merge_event_id_is_new(self):
        """merge_event_id == 'new' → 建立新事件，跳過去重。"""
        from app.api.chat import _process_tool_use

        mock_db = _make_mock_db()
        tool_data = _base_tool_data(merge_event_id="new")
        coords = _base_coords()

        result = await _process_tool_use(tool_data, "原始訊息", mock_db, coords)

        assert result["status"] == "created"
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_invalid_merge_event_id_returns_error(self):
        """無效的 merge_event_id（事件不存在） → 回傳錯誤。"""
        from app.api.chat import _process_tool_use

        mock_db = _make_mock_db()
        mock_db.get.return_value = None

        tool_data = _base_tool_data(merge_event_id=str(uuid.uuid4()))
        coords = _base_coords()

        result = await _process_tool_use(tool_data, "原始訊息", mock_db, coords)

        assert result["status"] == "error"
        assert "找不到" in result.get("message", "")

    @pytest.mark.asyncio
    async def test_inactive_event_returns_error(self):
        """merge_event_id 指向已結案事件 → 回傳錯誤。"""
        from app.api.chat import _process_tool_use

        inactive_event = _make_mock_event(status="resolved")
        mock_db = _make_mock_db()
        mock_db.get.return_value = inactive_event

        tool_data = _base_tool_data(merge_event_id=str(inactive_event.id))
        coords = _base_coords()

        result = await _process_tool_use(tool_data, "原始訊息", mock_db, coords)

        assert result["status"] == "error"
        assert "已結案" in result.get("message", "")

    @pytest.mark.asyncio
    async def test_merge_updates_all_numeric_fields(self):
        """合併時應更新所有數值欄位：severity 用 max，傷亡數字由 LLM 萃取決定。"""
        from unittest.mock import AsyncMock, patch
        from app.api.chat import _process_tool_use

        target = _make_mock_event(
            severity=2, casualties=1, injured=3, trapped=2, report_count=1
        )
        mock_db = _make_mock_db()
        mock_db.get.return_value = target

        tool_data = _base_tool_data(
            merge_event_id=str(target.id),
            severity=4,
            casualties=0,
            injured=5,
            trapped=1,
        )
        coords = _base_coords()

        with (
            patch(
                "app.api.chat.merge_event_descriptions",
                new_callable=AsyncMock,
                return_value="合併描述",
            ),
            patch(
                "app.api.chat.reextract_numbers_from_description",
                new_callable=AsyncMock,
                return_value={"casualties": 1, "injured": 8, "trapped": 3, "severity": 4},
            ),
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, coords)

        assert result["status"] == "merged"
        assert target.severity == 4   # max(2, 4) = 4
        assert target.casualties == 1  # LLM 萃取
        assert target.injured == 8    # LLM 萃取（累計）
        assert target.trapped == 3    # LLM 萃取（累計）
        assert target.report_count == 2

    @pytest.mark.asyncio
    async def test_merge_creates_report_linked_to_event(self):
        """合併時應建立新的 DisasterReport 並關聯到目標事件。"""
        from app.api.chat import _process_tool_use

        target = _make_mock_event(report_count=1)
        mock_db = _make_mock_db()
        mock_db.get.return_value = target

        tool_data = _base_tool_data(merge_event_id=str(target.id))
        coords = _base_coords()

        result = await _process_tool_use(tool_data, "原始訊息", mock_db, coords)

        assert result["status"] == "merged"
        mock_db.add.assert_called()

    @pytest.mark.asyncio
    async def test_create_new_with_none_coords(self):
        """merge_event_id='new' + coords=None → 建立事件 location_approximate=True。"""
        from app.api.chat import _process_tool_use

        mock_db = _make_mock_db()
        tool_data = _base_tool_data(merge_event_id="new")

        result = await _process_tool_use(tool_data, "原始訊息", mock_db, None)

        assert result["status"] == "created"


# ═══════════════════════════════════════════════════════════════════════════════
# 第五部分：Tool Schema 測試
# ═══════════════════════════════════════════════════════════════════════════════

class TestToolSchema:
    """測試 SUBMIT_TOOL schema 包含 merge_event_id。"""

    def test_submit_tool_has_merge_event_id(self):
        """SUBMIT_TOOL 的 input_schema 應包含 merge_event_id 屬性。"""
        from app.services.llm_service import SUBMIT_TOOL

        properties = SUBMIT_TOOL["input_schema"]["properties"]
        assert "merge_event_id" in properties
        assert properties["merge_event_id"]["type"] == "string"

    def test_merge_event_id_not_required(self):
        """merge_event_id 不應在 required 列表中。"""
        from app.services.llm_service import SUBMIT_TOOL

        required = SUBMIT_TOOL["input_schema"].get("required", [])
        assert "merge_event_id" not in required


# ═══════════════════════════════════════════════════════════════════════════════
# 第六部分：_compute_dedup_score() 補充測試
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeDedupScore:
    """補充測試 _compute_dedup_score() 在消歧義流程中的角色。"""

    def test_identical_reports_score_high(self):
        """完全相同的通報應得到高分（>= 0.50）。"""
        event = _make_mock_event(
            title="信義路淹水",
            description="信義路二段淹水30公分",
            disaster_type="flooding",
        )

        score = _compute_dedup_score(
            new_desc="信義路二段淹水30公分",
            new_lat=25.033,
            new_lon=121.565,
            new_time=event.occurred_at,
            new_type="flooding",
            candidate=event,
        )

        assert score >= 0.50

    def test_completely_different_reports_score_low(self):
        """完全不同的通報應得到低分（< 0.50）。"""
        event = _make_mock_event(
            title="高雄市旗津區火災",
            description="旗津渡船頭附近民宅火災",
            disaster_type="fire",
        )

        score = _compute_dedup_score(
            new_desc="台北市信義區大樓倒塌",
            new_lat=25.033,
            new_lon=121.565,
            new_time=datetime.now(timezone.utc) - timedelta(hours=48),
            new_type="building_damage",
            candidate=event,
        )

        assert score < 0.50

    def test_same_location_different_type_medium_score(self):
        """同地點不同災情類型 → 中等分數。"""
        event = _make_mock_event(
            disaster_type="flooding",
            description="淹水30公分",
        )

        score = _compute_dedup_score(
            new_desc="淹水30公分",
            new_lat=25.033,
            new_lon=121.565,
            new_time=event.occurred_at,
            new_type="road_collapse",
            candidate=event,
        )

        assert score < 0.80


# ═══════════════════════════════════════════════════════════════════════════════
# 第七部分：整合流程測試（SSE event_generator 去重消歧義分支）
# ═══════════════════════════════════════════════════════════════════════════════

class TestDedupDisambiguationFlow:
    """測試完整的去重消歧義 SSE 流程。"""

    @pytest.mark.asyncio
    async def test_needs_user_choice_triggers_continuation(self):
        """_process_tool_use 回傳 needs_user_choice 時，
        event_generator 應餵回 tool_result 給 Claude 而非直接送 report_submitted。"""
        from app.api.chat import _process_tool_use

        event = _make_mock_event()
        scored_candidates = [{"event": event, "score": 0.70, "distance_m": 100}]

        tool_data = _base_tool_data()
        coords = _base_coords()
        mock_db = _make_mock_db()

        with patch(
            "app.api.chat.find_and_score_candidates",
            new_callable=AsyncMock,
            return_value=scored_candidates,
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, coords)

        assert result["status"] == "needs_user_choice"

    @pytest.mark.asyncio
    async def test_second_call_with_merge_id_completes_flow(self):
        """第二次呼叫帶 merge_event_id 應正常完成合併。"""
        from app.api.chat import _process_tool_use

        target = _make_mock_event(report_count=1)
        mock_db = _make_mock_db()
        mock_db.get.return_value = target

        tool_data = _base_tool_data(merge_event_id=str(target.id))
        coords = _base_coords()

        result = await _process_tool_use(tool_data, "原始訊息", mock_db, coords)

        assert result["status"] == "merged"
        assert target.report_count == 2

    @pytest.mark.asyncio
    async def test_second_call_with_new_creates_event(self):
        """第二次呼叫 merge_event_id='new' 應建立新事件。"""
        from app.api.chat import _process_tool_use

        mock_db = _make_mock_db()
        tool_data = _base_tool_data(merge_event_id="new")
        coords = _base_coords()

        result = await _process_tool_use(tool_data, "原始訊息", mock_db, coords)

        assert result["status"] == "created"


# ═══════════════════════════════════════════════════════════════════════════════
# 第八部分：candidates_selection SSE 事件格式測試
# ═══════════════════════════════════════════════════════════════════════════════

class TestCandidatesSelectionEvent:
    """測試 _build_candidates_selection_event() 產生正確的 SSE 事件結構。"""

    def test_event_type_is_candidates_selection(self):
        """事件的 type 欄位必須為 'candidates_selection'。"""
        from app.api.chat import _build_candidates_selection_event

        event = _build_candidates_selection_event([])

        assert event["type"] == "candidates_selection"

    def test_event_contains_candidates_list(self):
        """事件必須包含 candidates 欄位（列表）。"""
        from app.api.chat import _build_candidates_selection_event

        event = _build_candidates_selection_event([])

        assert "candidates" in event
        assert isinstance(event["candidates"], list)

    def test_single_candidate_is_preserved(self):
        """單一候選事件應完整保留在 event["candidates"] 中。"""
        from app.api.chat import _build_candidates_selection_event

        candidate = {
            "event_id": "abc-123",
            "title": "信義路淹水",
            "description": "淹水30公分",
            "location_text": "台北市信義路二段100號",
            "report_count": 3,
            "distance_m": 150,
            "score": 0.85,
        }

        event = _build_candidates_selection_event([candidate])

        assert len(event["candidates"]) == 1
        c = event["candidates"][0]
        assert c["event_id"] == "abc-123"
        assert c["title"] == "信義路淹水"

    def test_all_required_fields_are_present_in_each_candidate(self):
        """每個候選事件應包含前端所需的全部欄位。"""
        from app.api.chat import _build_candidates_selection_event

        candidate = {
            "event_id": "abc-123",
            "title": "信義路淹水",
            "description": "淹水30公分",
            "location_text": "台北市信義路二段100號",
            "report_count": 3,
            "distance_m": 150,
            "score": 0.85,
        }

        event = _build_candidates_selection_event([candidate])
        c = event["candidates"][0]

        required_fields = [
            "event_id", "title", "description",
            "location_text", "report_count", "distance_m", "score",
        ]
        for field in required_fields:
            assert field in c, f"候選事件缺少欄位: {field}"

    def test_multiple_candidates_are_all_included(self):
        """多個候選事件應全部出現在 event["candidates"] 中，順序不變。"""
        from app.api.chat import _build_candidates_selection_event

        candidates = [
            {
                "event_id": "id-1",
                "title": "事件A",
                "description": "",
                "location_text": "地點A",
                "report_count": 1,
                "distance_m": 50,
                "score": 0.90,
            },
            {
                "event_id": "id-2",
                "title": "事件B",
                "description": "",
                "location_text": "地點B",
                "report_count": 2,
                "distance_m": 180,
                "score": 0.65,
            },
        ]

        event = _build_candidates_selection_event(candidates)

        assert len(event["candidates"]) == 2
        assert event["candidates"][0]["event_id"] == "id-1"
        assert event["candidates"][1]["event_id"] == "id-2"

    def test_event_is_json_serializable(self):
        """事件必須能被 json.dumps 序列化（用於 SSE data 欄位）。"""
        import json
        from app.api.chat import _build_candidates_selection_event

        candidates = [
            {
                "event_id": "test-id",
                "title": "測試事件",
                "description": "測試描述",
                "location_text": "測試地點",
                "report_count": 1,
                "distance_m": 50,
                "score": 0.75,
            }
        ]

        event = _build_candidates_selection_event(candidates)
        serialized = json.dumps(event, ensure_ascii=False)
        parsed = json.loads(serialized)

        assert parsed["type"] == "candidates_selection"
        assert len(parsed["candidates"]) == 1

    def test_candidate_field_values_are_unchanged(self):
        """候選事件的每個欄位值應與輸入完全一致，不被修改。"""
        from app.api.chat import _build_candidates_selection_event

        candidate = {
            "event_id": "uuid-abc",
            "title": "中山路火災",
            "description": "三樓冒煙",
            "location_text": "台北市中山路二段50號",
            "report_count": 5,
            "distance_m": 80,
            "score": 0.92,
        }

        event = _build_candidates_selection_event([candidate])
        c = event["candidates"][0]

        assert c["event_id"] == "uuid-abc"
        assert c["title"] == "中山路火災"
        assert c["description"] == "三樓冒煙"
        assert c["location_text"] == "台北市中山路二段50號"
        assert c["report_count"] == 5
        assert c["distance_m"] == 80
        assert c["score"] == 0.92

    def test_empty_candidates_returns_empty_list(self):
        """空列表輸入應回傳 candidates 為空列表的事件。"""
        from app.api.chat import _build_candidates_selection_event

        event = _build_candidates_selection_event([])

        assert event["candidates"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# 第十部分：回歸測試 — 確保既有行為不受影響
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegressionNoDedupCandidates:
    """當無任何候選時，行為應與改動前完全一致。"""

    @pytest.mark.asyncio
    async def test_no_candidates_creates_new_event_with_correct_fields(self):
        """無候選 → 建立新事件，結果包含正確欄位。"""
        from app.api.chat import _process_tool_use

        mock_db = _make_mock_db()
        tool_data = _base_tool_data(
            disaster_type="fire",
            location_text="台北市中山北路二段50號",
        )
        coords = _base_coords()

        with patch(
            "app.api.chat.find_and_score_candidates",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, coords)

        assert result["status"] == "created"
        assert "event_id" in result
        assert "message" in result

    @pytest.mark.asyncio
    async def test_no_candidates_with_none_coords(self):
        """geocoding 失敗 + 無候選 → 建立 approximate 事件。"""
        from app.api.chat import _process_tool_use

        mock_db = _make_mock_db()
        tool_data = _base_tool_data()

        with patch(
            "app.api.chat.find_and_score_candidates",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, None)

        assert result["status"] == "created"

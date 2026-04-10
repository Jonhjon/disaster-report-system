"""
事件合併邏輯測試（_merge_into_event）

測試範圍：
1. 描述合併：兩段描述整合、空描述邊界處理
2. 傷亡數字更新：LLM 成功萃取時採用萃取值；LLM 失敗時 fallback 為累加
3. 嚴重程度：仍使用 max()（只升不降）
4. report_count：每次合併 +1
5. 邊界情況：coords=None、新通報無傷亡、既有事件數字為 0
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _make_mock_event(
    *,
    event_id=None,
    title="花蓮縣餅火警",
    disaster_type="fire",
    description="花蓮縣餅發生火災，火勢蔓延",
    location_text="花蓮火車站前站的花蓮縣餅",
    severity=3,
    report_count=1,
    status="reported",
    casualties=0,
    injured=3,
    trapped=0,
):
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
    event.occurred_at = datetime.now(timezone.utc)
    event.updated_at = datetime.now(timezone.utc)
    return event


def _make_mock_db():
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = []
    mock_db.get.return_value = None
    return mock_db


def _base_coords(**overrides):
    coords = {
        "latitude": 23.9882,
        "longitude": 121.6016,
        "display_name": "花蓮火車站前站的花蓮縣餅",
        "source": "google_places",
    }
    coords.update(overrides)
    return coords


def _merge_tool_data(event_id, **overrides):
    data = {
        "disaster_type": "fire",
        "description": "火勢逐漸縮小，另有3人燒傷",
        "location_text": "花蓮火車站前站的花蓮縣餅",
        "severity": 3,
        "casualties": 0,
        "injured": 3,
        "trapped": 0,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "merge_event_id": str(event_id),
    }
    data.update(overrides)
    return data


# ═══════════════════════════════════════════════════════════════════════════════
# 第一部分：描述合併
# ═══════════════════════════════════════════════════════════════════════════════

class TestMergeDescriptions:

    @pytest.mark.asyncio
    async def test_descriptions_merged_when_both_present(self):
        """既有描述和新描述都存在時，應呼叫 merge_event_descriptions 合併。"""
        from app.api.chat import _process_tool_use

        target = _make_mock_event(description="火勢往外蔓延，3人燒傷")
        mock_db = _make_mock_db()
        mock_db.get.return_value = target

        tool_data = _merge_tool_data(target.id, description="火勢逐漸縮小，又3人燒傷")

        with (
            patch(
                "app.api.chat.merge_event_descriptions",
                new_callable=AsyncMock,
                return_value="火勢先蔓延後逐漸縮小，共6人燒傷",
            ) as mock_merge,
            patch(
                "app.api.chat.reextract_numbers_from_description",
                new_callable=AsyncMock,
                return_value={"injured": 6, "casualties": 0, "trapped": 0},
            ),
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, _base_coords())

        assert result["status"] == "merged"
        mock_merge.assert_called_once_with("火勢往外蔓延，3人燒傷", "火勢逐漸縮小，又3人燒傷")
        assert target.description == "火勢先蔓延後逐漸縮小，共6人燒傷"

    @pytest.mark.asyncio
    async def test_new_description_used_when_existing_empty(self):
        """既有事件描述為空時，直接使用新描述（merge_event_descriptions 回傳 new）。"""
        from app.api.chat import _process_tool_use

        target = _make_mock_event(description="")
        mock_db = _make_mock_db()
        mock_db.get.return_value = target

        tool_data = _merge_tool_data(target.id, description="又3人燒傷，火勢縮小")

        with (
            patch(
                "app.api.chat.merge_event_descriptions",
                new_callable=AsyncMock,
                return_value="又3人燒傷，火勢縮小",
            ),
            patch(
                "app.api.chat.reextract_numbers_from_description",
                new_callable=AsyncMock,
                return_value={"injured": 3},
            ),
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, _base_coords())

        assert result["status"] == "merged"
        assert target.description == "又3人燒傷，火勢縮小"

    @pytest.mark.asyncio
    async def test_description_unchanged_when_new_is_empty(self):
        """新通報描述為空時，不應呼叫 merge_event_descriptions，既有描述保持不變。"""
        from app.api.chat import _process_tool_use

        target = _make_mock_event(description="原有描述")
        mock_db = _make_mock_db()
        mock_db.get.return_value = target

        tool_data = _merge_tool_data(target.id, description="")

        with (
            patch(
                "app.api.chat.merge_event_descriptions",
                new_callable=AsyncMock,
            ) as mock_merge,
            patch(
                "app.api.chat.reextract_numbers_from_description",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, _base_coords())

        assert result["status"] == "merged"
        mock_merge.assert_not_called()
        assert target.description == "原有描述"

    @pytest.mark.asyncio
    async def test_description_unchanged_when_new_is_whitespace_only(self):
        """新通報描述為空白字元時，不應合併。"""
        from app.api.chat import _process_tool_use

        target = _make_mock_event(description="原有描述")
        mock_db = _make_mock_db()
        mock_db.get.return_value = target

        tool_data = _merge_tool_data(target.id, description="   ")

        with (
            patch(
                "app.api.chat.merge_event_descriptions",
                new_callable=AsyncMock,
            ) as mock_merge,
            patch(
                "app.api.chat.reextract_numbers_from_description",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, _base_coords())

        assert result["status"] == "merged"
        mock_merge.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# 第二部分：LLM 成功萃取數字
# ═══════════════════════════════════════════════════════════════════════════════

class TestMergeNumbersLLMSuccess:

    @pytest.mark.asyncio
    async def test_additional_injured_cumulated_by_llm(self):
        """
        情境：第一筆3人受傷（既有），第二筆「又有3人燒傷」→ LLM 從合併描述萃取出6人。
        預期：injured = 6
        """
        from app.api.chat import _process_tool_use

        target = _make_mock_event(injured=3, casualties=0, trapped=0)
        mock_db = _make_mock_db()
        mock_db.get.return_value = target

        tool_data = _merge_tool_data(target.id, injured=3, description="又有3人燒傷")

        with (
            patch(
                "app.api.chat.merge_event_descriptions",
                new_callable=AsyncMock,
                return_value="原有3人燒傷，另有3人燒傷，共6人受傷",
            ),
            patch(
                "app.api.chat.reextract_numbers_from_description",
                new_callable=AsyncMock,
                return_value={"injured": 6, "casualties": 0, "trapped": 0},
            ),
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, _base_coords())

        assert result["status"] == "merged"
        assert target.injured == 6

    @pytest.mark.asyncio
    async def test_same_people_restated_not_doubled(self):
        """
        情境：同一批3人被重複通報（描述無「又」）→ LLM 萃取出3（非6）。
        預期：injured = 3（不重複計算）
        """
        from app.api.chat import _process_tool_use

        target = _make_mock_event(injured=3)
        mock_db = _make_mock_db()
        mock_db.get.return_value = target

        tool_data = _merge_tool_data(target.id, injured=3, description="現場有3人燒傷")

        with (
            patch(
                "app.api.chat.merge_event_descriptions",
                new_callable=AsyncMock,
                return_value="現場3人燒傷（同批傷者）",
            ),
            patch(
                "app.api.chat.reextract_numbers_from_description",
                new_callable=AsyncMock,
                return_value={"injured": 3, "casualties": 0, "trapped": 0},
            ),
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, _base_coords())

        assert result["status"] == "merged"
        assert target.injured == 3

    @pytest.mark.asyncio
    async def test_no_additive_keyword_treated_as_status_update(self):
        """
        情境：第二筆通報說「3 人嚴重燒傷」，無「又有」等新增詞彙。
        → 視為同批傷者傷情惡化（狀態更新），不累加。
        預期：injured = 3（非 6）
        """
        from app.api.chat import _process_tool_use

        target = _make_mock_event(injured=3, casualties=0, trapped=0)
        mock_db = _make_mock_db()
        mock_db.get.return_value = target

        tool_data = _merge_tool_data(target.id, injured=3, description="3人嚴重燒傷")

        with (
            patch(
                "app.api.chat.merge_event_descriptions",
                new_callable=AsyncMock,
                return_value="3 人嚴重燒傷（傷情惡化）",
            ),
            patch(
                "app.api.chat.reextract_numbers_from_description",
                new_callable=AsyncMock,
                return_value={"injured": 3, "casualties": 0, "trapped": 0},
            ),
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, _base_coords())

        assert result["status"] == "merged"
        assert target.injured == 3, "無新增詞彙時不應累加，應視為同批傷者更新"

    @pytest.mark.asyncio
    async def test_casualties_and_trapped_updated_by_llm(self):
        """死亡和受困人數應由 LLM 萃取值更新。"""
        from app.api.chat import _process_tool_use

        target = _make_mock_event(casualties=1, injured=2, trapped=1)
        mock_db = _make_mock_db()
        mock_db.get.return_value = target

        tool_data = _merge_tool_data(
            target.id,
            casualties=2,
            injured=3,
            trapped=2,
            description="又有2人死亡、3人受傷、2人受困",
        )

        with (
            patch(
                "app.api.chat.merge_event_descriptions",
                new_callable=AsyncMock,
                return_value="累計3人死亡、5人受傷、3人受困",
            ),
            patch(
                "app.api.chat.reextract_numbers_from_description",
                new_callable=AsyncMock,
                return_value={"casualties": 3, "injured": 5, "trapped": 3},
            ),
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, _base_coords())

        assert result["status"] == "merged"
        assert target.casualties == 3
        assert target.injured == 5
        assert target.trapped == 3

    @pytest.mark.asyncio
    async def test_null_fields_in_llm_response_not_overwritten(self):
        """
        LLM 萃取結果中某欄位為 null（不在 dict 中）→ 對應欄位不應被覆蓋。
        """
        from app.api.chat import _process_tool_use

        target = _make_mock_event(casualties=2, injured=3, trapped=1)
        mock_db = _make_mock_db()
        mock_db.get.return_value = target

        tool_data = _merge_tool_data(target.id, description="火勢更大了")

        with (
            patch(
                "app.api.chat.merge_event_descriptions",
                new_callable=AsyncMock,
                return_value="火勢更大了",
            ),
            patch(
                "app.api.chat.reextract_numbers_from_description",
                new_callable=AsyncMock,
                # 只有 injured，沒有 casualties 和 trapped
                return_value={"injured": 4},
            ),
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, _base_coords())

        assert result["status"] == "merged"
        assert target.injured == 4
        # casualties 和 trapped 未在萃取結果中 → 應保持原值
        assert target.casualties == 2
        assert target.trapped == 1

    @pytest.mark.asyncio
    async def test_zero_value_from_llm_applied(self):
        """LLM 萃取值為 0 時應正常套用（表示確認無傷亡）。"""
        from app.api.chat import _process_tool_use

        target = _make_mock_event(casualties=0, injured=3, trapped=0)
        mock_db = _make_mock_db()
        mock_db.get.return_value = target

        tool_data = _merge_tool_data(target.id, description="傷者已送醫，無新增傷亡")

        with (
            patch(
                "app.api.chat.merge_event_descriptions",
                new_callable=AsyncMock,
                return_value="3人燒傷已送醫，無新增傷亡",
            ),
            patch(
                "app.api.chat.reextract_numbers_from_description",
                new_callable=AsyncMock,
                return_value={"casualties": 0, "injured": 3, "trapped": 0},
            ),
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, _base_coords())

        assert result["status"] == "merged"
        assert target.casualties == 0
        assert target.injured == 3
        assert target.trapped == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 第三部分：LLM 失敗 → fallback 累加
# ═══════════════════════════════════════════════════════════════════════════════

class TestMergeNumbersFallback:

    @pytest.mark.asyncio
    async def test_fallback_cumulates_injured_when_llm_returns_empty(self):
        """
        reextract 回傳空 dict → fallback 為 += 累加。
        3(既有) + 3(新增) = 6
        """
        from app.api.chat import _process_tool_use

        target = _make_mock_event(injured=3, casualties=0, trapped=0)
        mock_db = _make_mock_db()
        mock_db.get.return_value = target

        tool_data = _merge_tool_data(target.id, injured=3, casualties=0, trapped=0)

        with (
            patch(
                "app.api.chat.merge_event_descriptions",
                new_callable=AsyncMock,
                return_value="合併描述",
            ),
            patch(
                "app.api.chat.reextract_numbers_from_description",
                new_callable=AsyncMock,
                return_value={},  # 空 dict → fallback
            ),
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, _base_coords())

        assert result["status"] == "merged"
        assert target.injured == 6  # 3 + 3

    @pytest.mark.asyncio
    async def test_fallback_cumulates_all_fields(self):
        """fallback 時 casualties、injured、trapped 均累加。"""
        from app.api.chat import _process_tool_use

        target = _make_mock_event(casualties=1, injured=2, trapped=1)
        mock_db = _make_mock_db()
        mock_db.get.return_value = target

        tool_data = _merge_tool_data(
            target.id,
            casualties=2,
            injured=3,
            trapped=2,
        )

        with (
            patch(
                "app.api.chat.merge_event_descriptions",
                new_callable=AsyncMock,
                return_value="合併描述",
            ),
            patch(
                "app.api.chat.reextract_numbers_from_description",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, _base_coords())

        assert result["status"] == "merged"
        assert target.casualties == 3  # 1 + 2
        assert target.injured == 5     # 2 + 3
        assert target.trapped == 3     # 1 + 2

    @pytest.mark.asyncio
    async def test_fallback_when_reextract_raises_exception(self):
        """reextract 拋出例外 → 應被 except 捕捉，走 fallback 累加。"""
        from app.api.chat import _process_tool_use

        target = _make_mock_event(injured=3, casualties=0, trapped=0)
        mock_db = _make_mock_db()
        mock_db.get.return_value = target

        tool_data = _merge_tool_data(target.id, injured=2)

        reextract_mock = AsyncMock(side_effect=Exception("LLM API error"))

        with (
            patch(
                "app.api.chat.merge_event_descriptions",
                new_callable=AsyncMock,
                return_value="合併描述",
            ),
            patch(
                "app.api.chat.reextract_numbers_from_description",
                reextract_mock,
            ),
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, _base_coords())

        assert result["status"] == "merged"
        assert target.injured == 5  # fallback: 3 + 2

    @pytest.mark.asyncio
    async def test_fallback_when_merge_descriptions_raises_exception(self):
        """merge_event_descriptions 拋出例外時，仍能繼續執行並走 fallback。"""
        from app.api.chat import _process_tool_use

        target = _make_mock_event(description="原有描述", injured=3)
        mock_db = _make_mock_db()
        mock_db.get.return_value = target

        tool_data = _merge_tool_data(target.id, injured=2, description="新描述")

        with (
            patch(
                "app.api.chat.merge_event_descriptions",
                new_callable=AsyncMock,
                side_effect=Exception("LLM 描述合併失敗"),
            ),
            patch(
                "app.api.chat.reextract_numbers_from_description",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, _base_coords())

        assert result["status"] == "merged"
        assert target.injured == 5  # fallback: 3 + 2

    @pytest.mark.asyncio
    async def test_fallback_new_report_has_zero_casualties(self):
        """新通報傷亡皆為 0 時，fallback 累加後既有數字不變。"""
        from app.api.chat import _process_tool_use

        target = _make_mock_event(casualties=2, injured=4, trapped=1)
        mock_db = _make_mock_db()
        mock_db.get.return_value = target

        tool_data = _merge_tool_data(
            target.id,
            casualties=0,
            injured=0,
            trapped=0,
        )

        with (
            patch(
                "app.api.chat.merge_event_descriptions",
                new_callable=AsyncMock,
                return_value="合併描述",
            ),
            patch(
                "app.api.chat.reextract_numbers_from_description",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, _base_coords())

        assert result["status"] == "merged"
        assert target.casualties == 2  # 2 + 0
        assert target.injured == 4     # 4 + 0
        assert target.trapped == 1     # 1 + 0


# ═══════════════════════════════════════════════════════════════════════════════
# 第四部分：嚴重程度與 report_count
# ═══════════════════════════════════════════════════════════════════════════════

class TestMergeSeverityAndReportCount:

    @pytest.mark.asyncio
    async def test_severity_uses_max_llm_path(self):
        """LLM 萃取路徑：severity 採用 max(既有, 萃取值)。"""
        from app.api.chat import _process_tool_use

        target = _make_mock_event(severity=3)
        mock_db = _make_mock_db()
        mock_db.get.return_value = target

        tool_data = _merge_tool_data(target.id, severity=2)

        with (
            patch(
                "app.api.chat.merge_event_descriptions",
                new_callable=AsyncMock,
                return_value="描述",
            ),
            patch(
                "app.api.chat.reextract_numbers_from_description",
                new_callable=AsyncMock,
                return_value={"severity": 2, "injured": 3},
            ),
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, _base_coords())

        assert result["status"] == "merged"
        assert target.severity == 3  # max(3, 2) = 3，不降級

    @pytest.mark.asyncio
    async def test_severity_upgraded_when_new_is_higher_llm_path(self):
        """LLM 萃取路徑：新嚴重程度更高時應升級。"""
        from app.api.chat import _process_tool_use

        target = _make_mock_event(severity=2)
        mock_db = _make_mock_db()
        mock_db.get.return_value = target

        tool_data = _merge_tool_data(target.id, severity=5)

        with (
            patch(
                "app.api.chat.merge_event_descriptions",
                new_callable=AsyncMock,
                return_value="描述",
            ),
            patch(
                "app.api.chat.reextract_numbers_from_description",
                new_callable=AsyncMock,
                return_value={"severity": 5, "injured": 3},
            ),
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, _base_coords())

        assert result["status"] == "merged"
        assert target.severity == 5

    @pytest.mark.asyncio
    async def test_severity_uses_max_fallback_path(self):
        """fallback 路徑：severity 採用 max(既有, tool_data)。"""
        from app.api.chat import _process_tool_use

        target = _make_mock_event(severity=4)
        mock_db = _make_mock_db()
        mock_db.get.return_value = target

        tool_data = _merge_tool_data(target.id, severity=2)

        with (
            patch(
                "app.api.chat.merge_event_descriptions",
                new_callable=AsyncMock,
                return_value="描述",
            ),
            patch(
                "app.api.chat.reextract_numbers_from_description",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, _base_coords())

        assert result["status"] == "merged"
        assert target.severity == 4  # max(4, 2) = 4

    @pytest.mark.asyncio
    async def test_report_count_incremented_on_merge(self):
        """每次合併 report_count 應 +1。"""
        from app.api.chat import _process_tool_use

        target = _make_mock_event(report_count=3)
        mock_db = _make_mock_db()
        mock_db.get.return_value = target

        tool_data = _merge_tool_data(target.id)

        with (
            patch(
                "app.api.chat.merge_event_descriptions",
                new_callable=AsyncMock,
                return_value="描述",
            ),
            patch(
                "app.api.chat.reextract_numbers_from_description",
                new_callable=AsyncMock,
                return_value={"injured": 3},
            ),
        ):
            await _process_tool_use(tool_data, "原始訊息", mock_db, _base_coords())

        assert target.report_count == 4

    @pytest.mark.asyncio
    async def test_report_count_incremented_on_fallback(self):
        """fallback 路徑下 report_count 也應 +1。"""
        from app.api.chat import _process_tool_use

        target = _make_mock_event(report_count=1)
        mock_db = _make_mock_db()
        mock_db.get.return_value = target

        tool_data = _merge_tool_data(target.id)

        with (
            patch(
                "app.api.chat.merge_event_descriptions",
                new_callable=AsyncMock,
                return_value="描述",
            ),
            patch(
                "app.api.chat.reextract_numbers_from_description",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            await _process_tool_use(tool_data, "原始訊息", mock_db, _base_coords())

        assert target.report_count == 2


# ═══════════════════════════════════════════════════════════════════════════════
# 第五部分：邊界情況
# ═══════════════════════════════════════════════════════════════════════════════

class TestMergeEdgeCases:

    @pytest.mark.asyncio
    async def test_merge_with_coords_none(self):
        """coords=None 時應使用預設座標，合併仍應成功。"""
        from app.api.chat import _process_tool_use

        target = _make_mock_event()
        mock_db = _make_mock_db()
        mock_db.get.return_value = target

        tool_data = _merge_tool_data(target.id)

        with (
            patch(
                "app.api.chat.merge_event_descriptions",
                new_callable=AsyncMock,
                return_value="描述",
            ),
            patch(
                "app.api.chat.reextract_numbers_from_description",
                new_callable=AsyncMock,
                return_value={"injured": 3},
            ),
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, None)

        assert result["status"] == "merged"

    @pytest.mark.asyncio
    async def test_merge_when_existing_event_numbers_are_zero(self):
        """既有事件所有傷亡為 0 時，新通報數字應正確套用。"""
        from app.api.chat import _process_tool_use

        target = _make_mock_event(casualties=0, injured=0, trapped=0)
        mock_db = _make_mock_db()
        mock_db.get.return_value = target

        tool_data = _merge_tool_data(target.id, casualties=1, injured=5, trapped=2)

        with (
            patch(
                "app.api.chat.merge_event_descriptions",
                new_callable=AsyncMock,
                return_value="描述",
            ),
            patch(
                "app.api.chat.reextract_numbers_from_description",
                new_callable=AsyncMock,
                return_value={"casualties": 1, "injured": 5, "trapped": 2},
            ),
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, _base_coords())

        assert result["status"] == "merged"
        assert target.casualties == 1
        assert target.injured == 5
        assert target.trapped == 2

    @pytest.mark.asyncio
    async def test_db_commit_called_after_merge(self):
        """合併後應呼叫 db.commit() 將變更寫入資料庫。"""
        from app.api.chat import _process_tool_use

        target = _make_mock_event()
        mock_db = _make_mock_db()
        mock_db.get.return_value = target

        tool_data = _merge_tool_data(target.id)

        with (
            patch(
                "app.api.chat.merge_event_descriptions",
                new_callable=AsyncMock,
                return_value="描述",
            ),
            patch(
                "app.api.chat.reextract_numbers_from_description",
                new_callable=AsyncMock,
                return_value={"injured": 3},
            ),
        ):
            await _process_tool_use(tool_data, "原始訊息", mock_db, _base_coords())

        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_merge_result_contains_correct_event_id(self):
        """合併結果應回傳正確的 event_id。"""
        from app.api.chat import _process_tool_use

        target_id = uuid.uuid4()
        target = _make_mock_event(event_id=target_id)
        mock_db = _make_mock_db()
        mock_db.get.return_value = target

        tool_data = _merge_tool_data(target_id)

        with (
            patch(
                "app.api.chat.merge_event_descriptions",
                new_callable=AsyncMock,
                return_value="描述",
            ),
            patch(
                "app.api.chat.reextract_numbers_from_description",
                new_callable=AsyncMock,
                return_value={"injured": 3},
            ),
        ):
            result = await _process_tool_use(tool_data, "原始訊息", mock_db, _base_coords())

        assert result["status"] == "merged"
        assert result["event_id"] == str(target_id)

    @pytest.mark.asyncio
    async def test_reextract_called_with_merged_description(self):
        """reextract_numbers_from_description 應以合併後的描述（而非原始描述）作為輸入。"""
        from app.api.chat import _process_tool_use

        target = _make_mock_event(description="原有描述")
        mock_db = _make_mock_db()
        mock_db.get.return_value = target

        tool_data = _merge_tool_data(target.id, description="新描述")

        reextract_mock = AsyncMock(return_value={"injured": 3})

        with (
            patch(
                "app.api.chat.merge_event_descriptions",
                new_callable=AsyncMock,
                return_value="合併後的完整描述",
            ),
            patch(
                "app.api.chat.reextract_numbers_from_description",
                reextract_mock,
            ),
        ):
            await _process_tool_use(tool_data, "原始訊息", mock_db, _base_coords())

        reextract_mock.assert_called_once_with("合併後的完整描述")

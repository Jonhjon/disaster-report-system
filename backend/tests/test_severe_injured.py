"""重傷人數 severe_injured 的驗證、夾擠與重萃取測試。

對應手動測試案例分類：
- B：SubmitDisasterReportPayload 夾擠 / EventUpdate 跨欄驗證
- C：合併事件後 severe_injured <= injured 不變式
- D：reextract_numbers_from_description 抽取 severe_injured 與夾擠
"""
from datetime import datetime, timezone

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import ValidationError

from app.schemas.llm_tools import SubmitDisasterReportPayload
from app.schemas.event import EventUpdate
from app.services.llm_service import reextract_numbers_from_description


def _payload(**overrides) -> dict:
    """組出合法的 submit payload，測試個別欄位時以 overrides 覆寫。"""
    base = {
        "disaster_type": "fire",
        "description": "測試災情描述",
        "location_text": "台北市信義區松仁路100號",
        "severity": 3,
        "reporter_name": "測試者",
        "reporter_phone": "0900000000",
    }
    base.update(overrides)
    return base


# ── B. SubmitDisasterReportPayload 夾擠 ──────────────────────────────────────

def test_payload_keeps_valid_severe_injured():
    """B1：severe_injured <= injured → 原值保留"""
    p = SubmitDisasterReportPayload.model_validate(_payload(injured=5, severe_injured=2))
    assert p.injured == 5
    assert p.severe_injured == 2


def test_payload_clamps_severe_injured_over_injured():
    """B2：severe_injured > injured → 夾擠成 injured"""
    p = SubmitDisasterReportPayload.model_validate(_payload(injured=3, severe_injured=10))
    assert p.severe_injured == 3


def test_payload_defaults_severe_injured_to_zero():
    """B3：未提供 severe_injured → 預設 0"""
    p = SubmitDisasterReportPayload.model_validate(_payload(injured=4))
    assert p.severe_injured == 0


def test_payload_injured_zero_forces_severe_zero():
    """B4：injured=0 時 severe_injured 一律夾成 0"""
    p = SubmitDisasterReportPayload.model_validate(_payload(injured=0, severe_injured=3))
    assert p.severe_injured == 0


def test_payload_equal_severe_and_injured_allowed():
    """全部受傷都是重傷：severe == injured 合法"""
    p = SubmitDisasterReportPayload.model_validate(_payload(injured=4, severe_injured=4))
    assert p.severe_injured == 4


def test_payload_rejects_negative_severe_injured():
    """負數不合法（Field ge=0）"""
    with pytest.raises(ValidationError):
        SubmitDisasterReportPayload.model_validate(_payload(injured=2, severe_injured=-1))


# ── B. EventUpdate 跨欄驗證 ───────────────────────────────────────────────────

def test_eventupdate_accepts_valid_pair():
    """B5：injured 與 severe_injured 皆提供且合法 → 通過"""
    u = EventUpdate(injured=4, severe_injured=2)
    assert u.injured == 4
    assert u.severe_injured == 2


def test_eventupdate_rejects_severe_over_injured():
    """B6：severe_injured > injured → 422（ValidationError）"""
    with pytest.raises(ValidationError):
        EventUpdate(injured=4, severe_injured=9)


def test_eventupdate_allows_severe_only_without_injured():
    """B7：只更新 severe_injured（未帶 injured）→ 跨欄驗證不觸發，通過"""
    u = EventUpdate(severe_injured=2)
    assert u.severe_injured == 2
    assert u.injured is None


def test_eventupdate_equal_pair_allowed():
    """severe == injured 邊界合法"""
    u = EventUpdate(injured=3, severe_injured=3)
    assert u.severe_injured == 3


# ── C. 合併事件後 severe_injured <= injured 不變式 ───────────────────────────
#
# 合併的「覆寫」分支（reextract 成功）會各自獨立更新 injured 與 severe_injured。
# 當 reextract 只回傳其中一個欄位（部分抽取）時，另一欄保留事件現值，
# 可能使 severe_injured > injured，破壞「重傷是受傷子集」不變式。
# 累加分支數學上安全（各來源 severe<=injured，相加後仍成立），故不在此測試。


def _target_event(*, injured: int, severe_injured: int):
    """建立可被 _merge_into_event 操作的 target event mock。"""
    import uuid

    ev = MagicMock()
    ev.id = uuid.uuid4()
    ev.title = "信義路建物受損"
    ev.report_count = 1
    ev.severity = 3
    ev.casualties = 0
    ev.injured = injured
    ev.severe_injured = severe_injured
    ev.trapped = 0
    ev.status = "reported"
    ev.description = "信義路五段7號建物受損，2人受傷其中1人重傷。"
    ev.location_text = "台北市信義區信義路五段7號"
    ev.occurred_at = datetime.now(timezone.utc)
    ev.occurred_at_approximate = False
    return ev


def _merge_tool_data(**overrides) -> SubmitDisasterReportPayload:
    base = {
        "disaster_type": "building_damage",
        "description": "又有重傷傷者送醫。",
        "location_text": "台北市信義區信義路五段7號",
        "severity": 3,
        "injured": 0,
        "severe_injured": 0,
        "reporter_name": "測試者",
        "reporter_phone": "0900000000",
    }
    base.update(overrides)
    return SubmitDisasterReportPayload.model_validate(base)


@pytest.mark.asyncio
async def test_merge_partial_reextract_severe_without_injured_keeps_invariant(mock_db):
    """C3-a：reextract 只回傳 severe_injured（無 injured）→ 合併後仍須 severe <= injured"""
    from app.api import chat as chat_mod

    target = _target_event(injured=2, severe_injured=1)

    with patch.object(
        chat_mod, "reextract_numbers_from_description",
        new=AsyncMock(return_value={"severe_injured": 3}),   # 部分抽取，無 injured
    ), patch.object(
        chat_mod, "merge_event_descriptions",
        new=AsyncMock(return_value="合併後描述"),
    ):
        await chat_mod._merge_into_event(
            target,
            _merge_tool_data(),
            "又有一位重傷者送醫",
            mock_db,
            {"display_name": "台北市信義區信義路五段7號", "latitude": 25.03, "longitude": 121.56},
            datetime.now(timezone.utc),
            False,
        )

    assert target.severe_injured <= target.injured, (
        f"不變式被破壞：severe_injured={target.severe_injured} > injured={target.injured}"
    )


@pytest.mark.asyncio
async def test_merge_reextract_lowers_injured_below_existing_severe_keeps_invariant(mock_db):
    """C3-b：reextract 下修 injured（無 severe）→ 舊 severe 不得高於新 injured"""
    from app.api import chat as chat_mod

    target = _target_event(injured=5, severe_injured=3)

    with patch.object(
        chat_mod, "reextract_numbers_from_description",
        new=AsyncMock(return_value={"injured": 1}),   # 下修 injured，無 severe
    ), patch.object(
        chat_mod, "merge_event_descriptions",
        new=AsyncMock(return_value="合併後描述"),
    ):
        await chat_mod._merge_into_event(
            target,
            _merge_tool_data(),
            "更新：僅1人受傷",
            mock_db,
            {"display_name": "台北市信義區信義路五段7號", "latitude": 25.03, "longitude": 121.56},
            datetime.now(timezone.utc),
            False,
        )

    assert target.severe_injured <= target.injured, (
        f"不變式被破壞：severe_injured={target.severe_injured} > injured={target.injured}"
    )


# ── D. reextract_numbers_from_description 抽取 severe_injured ─────────────────

@pytest.mark.asyncio
async def test_reextract_extracts_severe_injured():
    """D1：LLM 回傳含 severe_injured → 正確萃取"""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(
        text='{"casualties":0,"injured":6,"severe_injured":3,"trapped":0,"severity":3}'
    )]
    with patch("app.services.llm_service.get_anthropic_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get.return_value = mock_client

        result = await reextract_numbers_from_description("共6人受傷，其中3人重傷")

    assert result["injured"] == 6
    assert result["severe_injured"] == 3


@pytest.mark.asyncio
async def test_reextract_clamps_severe_injured_over_injured():
    """D4：LLM 誤報 severe_injured > injured → 夾擠成 injured"""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(
        text='{"casualties":null,"injured":5,"severe_injured":8,"trapped":null,"severity":4}'
    )]
    with patch("app.services.llm_service.get_anthropic_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get.return_value = mock_client

        result = await reextract_numbers_from_description("5人受傷，8人重傷")

    assert result["injured"] == 5
    assert result["severe_injured"] == 5   # 夾擠


@pytest.mark.asyncio
async def test_reextract_severe_injured_null_omitted():
    """D3：severe_injured 為 null → 不放入 result（保留原值）"""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(
        text='{"casualties":null,"injured":3,"severe_injured":null,"trapped":null,"severity":2}'
    )]
    with patch("app.services.llm_service.get_anthropic_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get.return_value = mock_client

        result = await reextract_numbers_from_description("3人受傷")

    assert result["injured"] == 3
    assert "severe_injured" not in result


@pytest.mark.asyncio
async def test_reextract_grouped_injuries_sum_and_severe():
    """D2：分組傷者 → injured 加總、severe_injured 取重傷組"""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(
        text='{"casualties":0,"injured":6,"severe_injured":3,"trapped":0,"severity":3}'
    )]
    with patch("app.services.llm_service.get_anthropic_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get.return_value = mock_client

        result = await reextract_numbers_from_description("3人輕傷、3人重傷")

    assert result["injured"] == 6
    assert result["severe_injured"] == 3


# ── #1 管理端合併端點（events.py）的 severe 收斂 ─────────────────────────────

@pytest.mark.asyncio
async def test_admin_merge_endpoint_clamps_severe_injured(mock_db):
    """#1：管理端手動合併，reextract 部分抽取 → 合併後仍 severe <= injured"""
    from app.api import events as events_mod

    target = _target_event(injured=2, severe_injured=1)
    source = _target_event(injured=3, severe_injured=1)
    mock_db.get.side_effect = [target, source]

    with patch.object(
        events_mod, "reextract_numbers_from_description",
        new=AsyncMock(return_value={"severe_injured": 3}),   # 部分抽取，無 injured
    ), patch.object(
        events_mod, "merge_event_descriptions",
        new=AsyncMock(return_value="合併後描述"),
    ), patch.object(
        events_mod.event_service, "get_event_by_id",
        new=MagicMock(return_value=MagicMock()),
    ):
        await events_mod.merge_events(target.id, source.id, mock_db, MagicMock())

    assert target.severe_injured <= target.injured, (
        f"不變式被破壞：severe_injured={target.severe_injured} > injured={target.injured}"
    )


# ── #2 API 回傳序列化：_event_to_response 帶出 severe_injured ─────────────────

def _mock_db_event(**overrides):
    """建立可被 _event_to_response 讀取的 DisasterEvent-like mock。"""
    import uuid
    ev = MagicMock()
    ev.id = uuid.uuid4()
    ev.title = "測試事件"
    ev.disaster_type = "fire"
    ev.severity = 3
    ev.description = "描述"
    ev.location_text = "台北市信義區"
    ev.lat = 25.03
    ev.lng = 121.56
    ev.occurred_at = datetime.now(timezone.utc)
    ev.casualties = 0
    ev.injured = 5
    ev.severe_injured = 2
    ev.trapped = 0
    ev.status = "reported"
    ev.report_count = 1
    ev.location_approximate = False
    ev.occurred_at_approximate = False
    ev.created_at = datetime.now(timezone.utc)
    ev.updated_at = datetime.now(timezone.utc)
    for k, v in overrides.items():
        setattr(ev, k, v)
    return ev


def test_event_to_response_includes_severe_injured():
    """#2：_event_to_response 應把 severe_injured 帶進 EventResponse"""
    from app.services.event_service import _event_to_response

    resp = _event_to_response(_mock_db_event(injured=5, severe_injured=2))

    assert resp.injured == 5
    assert resp.severe_injured == 2


def test_get_event_by_id_round_trips_severe_injured(mock_db):
    """#2：GET 單一事件的服務層 round-trip 帶出 severe_injured"""
    from app.services.event_service import get_event_by_id

    ev = _mock_db_event(injured=4, severe_injured=3)
    # get_event_by_id 取 (event, lat, lng) tuple
    mock_db.query.return_value.filter.return_value.first.return_value = (ev, ev.lat, ev.lng)

    resp = get_event_by_id(mock_db, ev.id)

    assert resp is not None
    assert resp.severe_injured == 3


# ── #3 PUT 編輯持久化 severe_injured ─────────────────────────────────────────

def test_update_event_persists_severe_injured(mock_db):
    """#3：EventUpdate 帶 severe_injured → 透過 setattr 寫入事件"""
    from app.services.event_service import update_event

    set_attrs: dict = {}

    class FakeEvent:
        id = None
        injured = 5
        severe_injured = 0

        def __setattr__(self, key, value):
            set_attrs[key] = value
            object.__setattr__(self, key, value)

    fake = FakeEvent()
    mock_db.query.return_value.filter.return_value.first.return_value = fake

    with patch("app.services.event_service.get_event_by_id") as mock_get:
        mock_get.return_value = MagicMock()
        update_event(mock_db, "some-id", EventUpdate(injured=5, severe_injured=2))

    assert set_attrs.get("severe_injured") == 2


# ── #4 合併累加分支（reextract 失敗）對 severe 使用 atomic SQL 累加 ───────────

def _resolve_atomic(attr_value, original: int):
    """解析 `DisasterEvent.col + delta` 的 BinaryExpression 對原值的作用。"""
    from sqlalchemy.sql.elements import BinaryExpression

    if not isinstance(attr_value, BinaryExpression):
        return attr_value
    right = attr_value.right
    delta = getattr(right, "value", None)
    if delta is None:
        delta = int(str(right))
    op = attr_value.operator.__name__
    if op == "add":
        return original + delta
    raise ValueError(f"unsupported op: {op}")


@pytest.mark.asyncio
async def test_merge_accumulate_branch_sums_severe_injured(mock_db):
    """#4：reextract 回 {} → 走累加分支，severe_injured 以 atomic SQL 累加"""
    from app.api import chat as chat_mod

    target = _target_event(injured=5, severe_injured=2)

    with patch.object(
        chat_mod, "reextract_numbers_from_description",
        new=AsyncMock(return_value={}),   # 空 → 觸發 else 累加分支
    ), patch.object(
        chat_mod, "merge_event_descriptions",
        new=AsyncMock(return_value="合併後描述"),
    ):
        await chat_mod._merge_into_event(
            target,
            _merge_tool_data(injured=3, severe_injured=1),
            "又有1人重傷",
            mock_db,
            {"display_name": "x", "latitude": 25.0, "longitude": 121.5},
            datetime.now(timezone.utc),
            False,
        )

    # 累加分支使用 DisasterEvent.severe_injured + tool_data.severe_injured（atomic）
    assert _resolve_atomic(target.severe_injured, 2) == 3   # 2 + 1

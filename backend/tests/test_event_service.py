"""
方向二：Event Service 業務邏輯（5 案例）
策略：Mock SQLAlchemy session，測試純 Python 邏輯
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.schemas.event import EventUpdate
from app.services.event_service import (
    get_event_by_id,
    get_events,
    get_map_events,
    update_event,
)


def _make_mock_query():
    """回傳支援常見查詢鏈的 MagicMock。"""
    q = MagicMock()
    q.filter.return_value = q
    q.count.return_value = 0
    q.order_by.return_value = q
    q.offset.return_value = q
    q.limit.return_value = q
    q.with_for_update.return_value = q
    q.all.return_value = []
    return q


def _make_mock_agg_query(one_value=None):
    """支援聚合查詢鏈的 MagicMock。

    既有的 _make_mock_query() 不夠用：with_entities / group_by 預設不回傳 self，
    one() 回傳 MagicMock 無法解包（TypeError: cannot unpack non-sequence MagicMock）。

    放在本檔（而非只放 test_statistics.py）的理由：get_events 未來重構成
    apply_event_filters 後，本檔既有測試也可能需要聚合查詢鏈的 mock；
    test_statistics.py 直接 import 這個 helper，避免兩份幾乎相同的程式碼漂移。
    """
    q = MagicMock()
    for m in ("filter", "with_entities", "group_by", "order_by", "offset", "limit"):
        getattr(q, m).return_value = q
    q.all.return_value = []
    # 預設回傳一列夠長的 0，讓呼叫端不論取用幾個聚合欄位都能索引到值。
    # 各聚合查詢的欄位數不同（summary 9 欄、resolution 5 欄），
    # 把長度綁死會讓 mock 反過來限制實作能放幾個聚合。
    q.one.return_value = one_value if one_value is not None else (0,) * 16
    q.scalar.return_value = 0
    q.count.return_value = 0
    return q


# ---------------------------------------------------------------------------
# 特徵化測試（characterization tests）：非 TDD 的 RED 部分。
#
# get_events 目前已經實作且行為正確，這兩條測試現在就是綠燈。
# 目的是在 apply_event_filters 重構（把 get_events 與未來的 stats_service.get_statistics
# 共用的篩選邏輯抽出）之前先釘住「7 個篩選條件 → 7 次 filter() 呼叫」這個不變量，
# 讓重構過程中若不小心漏掉或重複套用某個條件能立刻被抓到。
# ---------------------------------------------------------------------------
def test_get_events_all_filters_call_filter_seven_times():
    """特徵化測試（現在即為綠燈）：七個篩選條件同時提供 → filter() 恰好呼叫 7 次。"""
    mock_db = MagicMock()
    mock_query = _make_mock_query()
    mock_db.query.return_value = mock_query

    get_events(
        mock_db,
        search="測試地震",
        disaster_type="fire",
        severity_min=1,
        severity_max=5,
        status="reported",
        date_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        date_to=datetime(2026, 12, 31, tzinfo=timezone.utc),
    )

    assert mock_query.filter.call_count == 7


def test_get_events_no_filters_call_filter_zero_times():
    """特徵化測試（現在即為綠燈）：不帶任何篩選條件 → filter() 完全不被呼叫。"""
    mock_db = MagicMock()
    mock_query = _make_mock_query()
    mock_db.query.return_value = mock_query

    get_events(mock_db)

    assert mock_query.filter.call_count == 0


# Case 6: sort_by="severity" + sort_order="asc" → ORDER BY severity ASC
def test_get_events_sort_by_severity_asc():
    mock_db = MagicMock()
    mock_query = _make_mock_query()
    mock_db.query.return_value = mock_query

    get_events(mock_db, sort_by="severity", sort_order="asc")

    mock_query.order_by.assert_called_once()
    call_arg = mock_query.order_by.call_args[0][0]
    arg_str = str(call_arg).upper()
    assert "SEVERITY" in arg_str
    assert "ASC" in arg_str


# Case 7: page=2, page_size=5 → offset=5, limit=5
def test_get_events_pagination_offset_and_limit():
    mock_db = MagicMock()
    mock_query = _make_mock_query()
    mock_db.query.return_value = mock_query

    get_events(mock_db, page=2, page_size=5)

    mock_query.offset.assert_called_once_with(5)
    mock_query.limit.assert_called_once_with(5)


# Case 8: get_event_by_id ID 不存在 → 回傳 None
def test_get_event_by_id_not_found():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    result = get_event_by_id(mock_db, uuid4())

    assert result is None


# Case 9: get_map_events bounds="24.9,121.4,25.1,121.6" → ST_MakeEnvelope 正確呼叫
def test_get_map_events_with_bounds_calls_st_make_envelope():
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = []

    with patch("app.services.event_service.func") as mock_func:
        mock_func.ST_MakeEnvelope.return_value = MagicMock()
        mock_func.ST_Within.return_value = MagicMock()

        get_map_events(mock_db, bounds="24.9,121.4,25.1,121.6")

        # bounds 格式：south,west,north,east → ST_MakeEnvelope(west, south, east, north, srid)
        mock_func.ST_MakeEnvelope.assert_called_once_with(121.4, 24.9, 121.6, 25.1, 4326)


# Case 10: update_event 只更新 status，其餘欄位不變
def test_update_event_partial_status_only():
    event_id = uuid4()
    mock_db = MagicMock()

    set_attrs: dict = {}

    class FakeEvent:
        id = event_id
        title = "Original Title"
        severity = 2
        status = "reported"
        description = None
        casualties = 0
        injured = 0
        trapped = 0

        def __setattr__(self, key, value):
            set_attrs[key] = value
            object.__setattr__(self, key, value)

    fake_event = FakeEvent()
    query = mock_db.query.return_value.filter.return_value
    query.with_for_update.return_value = query
    query.first.return_value = fake_event

    with patch("app.services.event_service.get_event_by_id") as mock_get_by_id:
        mock_get_by_id.return_value = MagicMock()
        data = EventUpdate(status="in_progress")
        update_event(mock_db, event_id, data)

    assert "status" in set_attrs
    assert set_attrs["status"] == "in_progress"
    assert "title" not in set_attrs
    assert "severity" not in set_attrs


def _update_status_event(initial_status, initial_resolved_at, new_status, now):
    event_id = uuid4()
    event = MagicMock()
    event.status = initial_status
    event.resolved_at = initial_resolved_at
    mock_db = MagicMock()
    query = mock_db.query.return_value.filter.return_value
    query.with_for_update.return_value = query
    query.first.return_value = event

    with (
        patch("app.services.event_service.datetime") as mock_datetime,
        patch("app.services.event_service.get_event_by_id", return_value=MagicMock()),
    ):
        mock_datetime.now.return_value = now
        update_event(mock_db, event_id, EventUpdate(status=new_status))

    return event


def test_update_event_reported_to_resolved_records_timestamp():
    now = datetime(2026, 8, 1, 1, 2, 3, tzinfo=timezone.utc)

    event = _update_status_event("reported", None, "resolved", now)

    assert event.resolved_at == now


def test_update_event_staying_resolved_preserves_original_timestamp():
    original = datetime(2026, 7, 1, tzinfo=timezone.utc)
    later = datetime(2026, 8, 1, tzinfo=timezone.utc)

    event = _update_status_event("resolved", original, "resolved", later)

    assert event.resolved_at == original


def test_update_event_resolved_to_reopened_clears_timestamp():
    original = datetime(2026, 7, 1, tzinfo=timezone.utc)

    event = _update_status_event(
        "resolved", original, "in_progress", datetime.now(timezone.utc)
    )

    assert event.resolved_at is None


def test_update_event_reopened_to_resolved_records_new_timestamp():
    new_resolution = datetime(2026, 8, 2, tzinfo=timezone.utc)

    event = _update_status_event("in_progress", None, "resolved", new_resolution)

    assert event.resolved_at == new_resolution


def test_update_event_locks_row_before_reading_status_for_resolution_transition():
    """Concurrent status updates must derive resolved_at from a locked row."""
    event_id = uuid4()
    event = MagicMock()
    event.status = "reported"
    event.resolved_at = None
    mock_db = MagicMock()
    query = _make_mock_query()
    query.with_for_update.return_value = query
    query.first.return_value = event
    mock_db.query.return_value = query

    with patch("app.services.event_service.get_event_by_id", return_value=MagicMock()):
        update_event(mock_db, event_id, EventUpdate(status="resolved"))

    query.with_for_update.assert_called_once_with()
    method_names = [call[0] for call in query.method_calls]
    assert method_names.index("with_for_update") < method_names.index("first")


# Case 11: update_event 更新 occurred_at → 自動清除 occurred_at_approximate 旗標
def test_update_event_occurred_at_clears_approximate_flag():
    event_id = uuid4()
    mock_db = MagicMock()

    set_attrs: dict = {}

    class FakeEvent:
        id = event_id
        occurred_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        occurred_at_approximate = True

        def __setattr__(self, key, value):
            set_attrs[key] = value
            object.__setattr__(self, key, value)

    fake_event = FakeEvent()
    query = mock_db.query.return_value.filter.return_value
    query.with_for_update.return_value = query
    query.first.return_value = fake_event

    new_time = datetime(2026, 7, 20, 3, 0, tzinfo=timezone.utc)
    with patch("app.services.event_service.get_event_by_id") as mock_get_by_id:
        mock_get_by_id.return_value = MagicMock()
        data = EventUpdate(occurred_at=new_time)
        update_event(mock_db, event_id, data)

    assert set_attrs["occurred_at"] == new_time
    assert set_attrs["occurred_at_approximate"] is False


# Case 12: update_event 未更新 occurred_at → 不動 occurred_at_approximate 旗標
def test_update_event_without_occurred_at_keeps_approximate_flag():
    event_id = uuid4()
    mock_db = MagicMock()

    set_attrs: dict = {}

    class FakeEvent:
        id = event_id
        title = "Original Title"
        occurred_at_approximate = True

        def __setattr__(self, key, value):
            set_attrs[key] = value
            object.__setattr__(self, key, value)

    fake_event = FakeEvent()
    query = mock_db.query.return_value.filter.return_value
    query.with_for_update.return_value = query
    query.first.return_value = fake_event

    with patch("app.services.event_service.get_event_by_id") as mock_get_by_id:
        mock_get_by_id.return_value = MagicMock()
        data = EventUpdate(title="New Title")
        update_event(mock_db, event_id, data)

    assert set_attrs["title"] == "New Title"
    assert "occurred_at_approximate" not in set_attrs

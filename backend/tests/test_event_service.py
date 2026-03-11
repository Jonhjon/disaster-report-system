"""
方向二：Event Service 業務邏輯（5 案例）
策略：Mock SQLAlchemy session，測試純 Python 邏輯
"""
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
    q.all.return_value = []
    return q


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
        status = "active"
        description = None
        casualties = 0
        injured = 0
        trapped = 0

        def __setattr__(self, key, value):
            set_attrs[key] = value
            object.__setattr__(self, key, value)

    fake_event = FakeEvent()
    mock_db.query.return_value.filter.return_value.first.return_value = fake_event

    with patch("app.services.event_service.get_event_by_id") as mock_get_by_id:
        mock_get_by_id.return_value = MagicMock()
        data = EventUpdate(status="monitoring")
        update_event(mock_db, event_id, data)

    assert "status" in set_attrs
    assert set_attrs["status"] == "monitoring"
    assert "title" not in set_attrs
    assert "severity" not in set_attrs

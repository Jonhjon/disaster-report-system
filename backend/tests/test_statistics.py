"""
統計功能測試：純函式層 + service 層（MagicMock）+ API 層。

涵蓋純函式、查詢契約、CSV 安全性、匯出上限及 API 路由行為。
"""
import csv
import io
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.database import get_db
from app.services.stats_service import (
    MAX_TREND_BUCKETS,
    _query_resolution,
    build_export_rows,
    compute_percentages,
    fill_trend_gaps,
    get_statistics,
    seconds_to_hours,
    validate_timezone,
)
from tests.test_event_service import _make_mock_agg_query


# ---------------------------------------------------------------------------
# 純函式層：validate_timezone
# ---------------------------------------------------------------------------
def test_validate_timezone_valid_returns_original_value():
    assert validate_timezone("Asia/Taipei") == "Asia/Taipei"


def test_validate_timezone_invalid_raises_value_error():
    with pytest.raises(ValueError):
        validate_timezone("Not/AZone")


# ---------------------------------------------------------------------------
# 純函式層：seconds_to_hours
# ---------------------------------------------------------------------------
def test_seconds_to_hours_none_stays_none():
    """None 必須原樣回傳，不可 coalesce 成 0.0（0.0 代表「剛好 0 小時」，語意不同）。"""
    assert seconds_to_hours(None) is None


def test_seconds_to_hours_one_hour():
    assert seconds_to_hours(3600) == 1.0


def test_seconds_to_hours_one_point_five_hours():
    assert seconds_to_hours(5400) == 1.5


# ---------------------------------------------------------------------------
# 純函式層：compute_percentages
# ---------------------------------------------------------------------------
def test_compute_percentages_basic_ratio():
    result = compute_percentages([("fire", 3), ("flooding", 1)])

    assert len(result) == 2
    assert result[0].key == "fire"
    assert result[0].count == 3
    assert result[0].percentage == 75.0
    assert result[1].key == "flooding"
    assert result[1].count == 1
    assert result[1].percentage == 25.0


def test_compute_percentages_empty_input_returns_empty_list():
    assert compute_percentages([]) == []


def test_compute_percentages_all_zero_counts_returns_empty_list_no_zero_division():
    """總和為 0 時必須回傳空列表，不可丟 ZeroDivisionError。"""
    result = compute_percentages([("a", 0), ("b", 0)])
    assert result == []


# ---------------------------------------------------------------------------
# 純函式層：fill_trend_gaps
# ---------------------------------------------------------------------------
def test_fill_trend_gaps_day_fills_missing_dates_with_zero():
    rows = [(date(2026, 8, 1), 3), (date(2026, 8, 4), 2)]

    result = fill_trend_gaps(rows, "day")

    assert len(result) == 4
    starts = [p.bucket_start for p in result]
    counts = [p.count for p in result]
    assert starts == [date(2026, 8, 1), date(2026, 8, 2), date(2026, 8, 3), date(2026, 8, 4)]
    assert counts == [3, 0, 0, 2]
    # 依 bucket_start 遞增排序
    assert starts == sorted(starts)


def test_fill_trend_gaps_month_crosses_year_boundary():
    """12 月 → 1 月手動年月進位：年份必須 +1，不能滾成同年 13 月。"""
    rows = [(date(2025, 12, 1), 3), (date(2026, 1, 1), 2)]

    result = fill_trend_gaps(rows, "month")

    assert len(result) == 2
    assert result[0].bucket_start == date(2025, 12, 1)
    assert result[0].count == 3
    assert result[1].bucket_start == date(2026, 1, 1)
    assert result[1].count == 2


def test_fill_trend_gaps_week_steps_seven_days():
    """週分桶步進 7 天：兩筆已對齊週一的資料相隔兩週 → 補出中間一個空桶。"""
    rows = [(date(2026, 8, 3), 3), (date(2026, 8, 17), 2)]  # 兩者皆為週一

    result = fill_trend_gaps(rows, "week")

    starts = [p.bucket_start for p in result]
    counts = [p.count for p in result]
    assert starts == [date(2026, 8, 3), date(2026, 8, 10), date(2026, 8, 17)]
    assert counts == [3, 0, 2]


def test_fill_trend_gaps_week_aligns_start_to_monday():
    """單一非週一日期 → 序列起點須對齊到該週週一（8/5 是週三，該週週一是 8/3）。"""
    rows = [(date(2026, 8, 5), 4)]

    result = fill_trend_gaps(rows, "week")

    assert result[0].bucket_start.weekday() == 0  # Monday
    assert result[0].bucket_start == date(2026, 8, 3)


def test_fill_trend_gaps_with_explicit_start_end_covers_full_range_even_without_data():
    rows = [(date(2026, 8, 2), 5)]

    result = fill_trend_gaps(
        rows, "day", start=date(2026, 8, 1), end=date(2026, 8, 4)
    )

    starts = [p.bucket_start for p in result]
    counts = [p.count for p in result]
    assert starts == [date(2026, 8, 1), date(2026, 8, 2), date(2026, 8, 3), date(2026, 8, 4)]
    assert counts == [0, 5, 0, 0]


def test_fill_trend_gaps_empty_rows_without_start_end_returns_empty_list():
    """rows 為空且未指定 start/end → 回傳空列表（前端顯示空狀態），不是一整排 0。"""
    assert fill_trend_gaps([], "day") == []


def test_fill_trend_gaps_exceeding_max_buckets_raises_value_error():
    rows = [(date(2024, 1, 1), 1), (date(2026, 1, 1), 1)]

    with pytest.raises(ValueError):
        fill_trend_gaps(rows, "day", max_buckets=400)


def test_max_trend_buckets_constant_is_400():
    """契約常數，供 API 層與前端說明文件對齊。"""
    assert MAX_TREND_BUCKETS == 400


# ---------------------------------------------------------------------------
# Service 層：get_statistics（MagicMock db）
# ---------------------------------------------------------------------------
def test_get_statistics_all_filters_applied_via_shared_filter_logic():
    """七個篩選條件同時提供 → filter() 呼叫次數應是 7 的倍數。

    get_statistics 內部通常需要多條聚合查詢（summary / by_disaster_type /
    by_severity / by_status / trend / cross_tab / resolution），但篩選條件
    與 event_service.get_events 共用 apply_event_filters，所以無論內部建了
    幾條查詢，每條查詢套用篩選的次數都應該是 7（七個條件各一次 filter）。
    """
    mock_db = MagicMock()
    mock_query = _make_mock_agg_query()
    mock_db.query.return_value = mock_query

    get_statistics(
        mock_db,
        search="測試",
        disaster_type="fire",
        severity_min=1,
        severity_max=5,
        status="reported",
        date_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        date_to=datetime(2026, 12, 31, tzinfo=timezone.utc),
    )

    assert mock_query.filter.call_count > 0
    assert mock_query.filter.call_count % 7 == 0


def test_get_statistics_week_bucket_reflected_in_group_by_expression():
    """bucket="week" → 傳給 group_by 的 SQL 表達式字串應含 WEEK（比照既有風格）。"""
    mock_db = MagicMock()
    mock_query = _make_mock_agg_query()
    mock_db.query.return_value = mock_query

    get_statistics(mock_db, bucket="week")

    assert mock_query.group_by.call_count > 0
    call_arg = mock_query.group_by.call_args[0][0]
    assert "WEEK" in str(call_arg).upper()


def test_get_statistics_timezone_reflected_in_sql_expression():
    """tz="Asia/Taipei" → 時區必須被帶進分桶用的 SQL 表達式，否則會以 UTC 午夜切桶。"""
    mock_db = MagicMock()
    mock_query = _make_mock_agg_query()
    mock_db.query.return_value = mock_query

    get_statistics(mock_db, tz="Asia/Taipei")

    assert mock_query.group_by.call_count > 0
    call_arg = mock_query.group_by.call_args[0][0]
    assert "Asia/Taipei" in str(call_arg)


def test_get_statistics_invalid_timezone_raises_before_touching_db():
    """非法時區必須在碰 DB 之前就丟 ValueError（避免 Postgres InvalidParameterValue → 500）。"""
    mock_db = MagicMock()

    with pytest.raises(ValueError):
        get_statistics(mock_db, tz="Bad/Zone")

    mock_db.query.assert_not_called()


def test_statistics_db_starts_repeatable_read_read_only_snapshot_before_authentication(
    mocker,
):
    """The shared statistics session must establish its snapshot before yield."""
    from app.database import get_statistics_db

    mock_db = MagicMock()
    mocker.patch("app.database.SessionLocal", return_value=mock_db)

    dependency = get_statistics_db()
    yielded_db = next(dependency)

    assert yielded_db is mock_db
    mock_db.execute.assert_called_once()
    statement = str(mock_db.execute.call_args.args[0])
    normalized = " ".join(statement.upper().split())
    assert "SET TRANSACTION" in normalized
    assert "ISOLATION LEVEL REPEATABLE READ" in normalized
    assert "READ ONLY" in normalized
    dependency.close()
    mock_db.close.assert_called_once()


def test_resolution_aggregates_exclude_non_resolved_rows_with_resolved_at():
    """A stale resolved_at on an open row must not enter counts or durations."""
    mock_db = MagicMock()
    query = _make_mock_agg_query()
    mock_db.query.return_value = query

    _query_resolution(mock_db, {})

    aggregate_expressions = query.with_entities.call_args.args
    for index in (0, 2, 3, 4):
        expression_sql = str(aggregate_expressions[index]).lower()
        assert "status" in expression_sql
        assert "resolved" in expression_sql


def _mock_export_event(**overrides):
    values = {
        "id": "00000000-0000-0000-0000-000000000001",
        "title": "一般標題",
        "disaster_type": "fire",
        "severity": 3,
        "status": "reported",
        "location_text": "台北市信義區",
        "occurred_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
        "casualties": 0,
        "injured": 0,
        "severe_injured": 0,
        "trapped": 0,
        "report_count": 1,
        "location_approximate": False,
        "occurred_at_approximate": False,
        "created_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
        "resolved_at": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _build_export_with_event(event):
    mock_db = MagicMock()
    query = MagicMock()
    query.order_by.return_value = query
    query.limit.return_value = query
    query.all.return_value = [(event, 25.033, 121.565)]
    mock_db.query.return_value = query
    return build_export_rows(mock_db)


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@", "\t", "\r"])
@pytest.mark.parametrize(
    ("field", "column"),
    [("title", 1), ("location_text", 7)],
)
def test_export_neutralizes_formula_prefixes_in_user_text_fields(prefix, field, column):
    value = f"{prefix}SUM(1,1)"

    rows = _build_export_with_event(_mock_export_event(**{field: value}))

    assert rows[1][column] == f"'{value}"


def test_export_neutralizes_all_event_derived_text_columns():
    event = _mock_export_event(
        title="=title",
        disaster_type="+custom-type",
        status="-custom-status",
        location_text="@location",
    )

    rows = _build_export_with_event(event)

    assert [rows[1][index] for index in (1, 2, 3, 5, 6, 7)] == [
        "'=title",
        "'+custom-type",
        "'+custom-type",
        "'-custom-status",
        "'-custom-status",
        "'@location",
    ]


def test_export_preserves_normal_user_text():
    rows = _build_export_with_event(
        _mock_export_event(title="一般標題", location_text="台北市信義區")
    )

    assert rows[1][1] == "一般標題"
    assert rows[1][7] == "台北市信義區"


def test_export_order_uses_event_id_as_deterministic_tiebreaker():
    mock_db = MagicMock()
    query = _make_mock_agg_query()
    mock_db.query.return_value = query

    build_export_rows(mock_db, sort_by="severity", sort_order="desc")

    order_expressions = query.order_by.call_args.args
    assert len(order_expressions) == 2
    assert "severity" in str(order_expressions[0]).lower()
    assert "id" in str(order_expressions[1]).lower()


# ---------------------------------------------------------------------------
# API 層：GET /api/events/statistics, GET /api/events/export.csv
# ---------------------------------------------------------------------------
from app.schemas.statistics import (  # noqa: E402  (刻意放在檔案後段，緊鄰 API 層測試使用處)
    CategoryCount,
    CrossTabCell,
    ResolutionStats,
    StatisticsResponse,
    StatisticsSummary,
    TrendPoint,
)


def _make_stats_response() -> StatisticsResponse:
    return StatisticsResponse(
        summary=StatisticsSummary(
            total_events=10,
            total_report_count=15,
            total_casualties=1,
            total_injured=3,
            total_severe_injured=1,
            total_trapped=0,
            avg_severity=2.5,
            high_severity_count=2,
            unresolved_count=4,
        ),
        by_disaster_type=[CategoryCount(key="fire", count=7, percentage=70.0)],
        by_severity=[CategoryCount(key="3", count=10, percentage=100.0)],
        by_status=[CategoryCount(key="reported", count=10, percentage=100.0)],
        trend=[TrendPoint(bucket_start=date(2026, 8, 1), count=3)],
        cross_tab=[CrossTabCell(disaster_type="fire", severity=3, count=7)],
        resolution=ResolutionStats(
            resolved_count=0,
            legacy_excluded_count=0,
            avg_hours=None,
            median_hours=None,
            p90_hours=None,
        ),
        bucket="day",
        timezone="Asia/Taipei",
        generated_at=datetime(2026, 8, 6, 12, 0, 0, tzinfo=timezone.utc),
    )


def test_statistics_endpoint_returns_all_expected_keys(auth_client, mocker):
    mocker.patch(
        "app.api.events.stats_service.get_statistics",
        return_value=_make_stats_response(),
    )

    response = auth_client.get("/api/events/statistics")

    assert response.status_code == 200
    data = response.json()
    for key in (
        "summary",
        "by_disaster_type",
        "by_severity",
        "by_status",
        "trend",
        "cross_tab",
        "resolution",
        "bucket",
        "timezone",
        "generated_at",
    ):
        assert key in data


def test_statistics_route_holds_only_one_database_session_dependency():
    """Authentication must not retain a second connection during aggregation."""
    from app.database import get_statistics_db
    from app.main import app

    route = next(
        route
        for route in app.routes
        if getattr(route, "path", None) == "/api/events/statistics"
    )
    def dependency_calls(dependant):
        for dependency in dependant.dependencies:
            yield dependency.call
            yield from dependency_calls(dependency)

    session_dependencies = [
        dependency
        for dependency in dependency_calls(route.dependant)
        if dependency in {get_db, get_statistics_db}
    ]

    assert session_dependencies == [get_statistics_db]


def test_statistics_route_not_shadowed_by_event_id_route(auth_client):
    """路由順序回歸測試。

    若 `/events/statistics` 被宣告在 `/events/{event_id}` 之後，FastAPI 會
    優先拿 "statistics" 去匹配 `event_id: UUID`，因為不是合法 UUID 而回 422。
    一旦這條測試意外變綠燈但原因是 422 以外（例如 404，代表路由根本沒宣告），
    仍不算通過此檢查的本意；此測試只斷言「不是 422 這種 UUID 解析失敗」，
    路由是否存在由其他測試（如 test_statistics_endpoint_returns_all_expected_keys）
    負責把關。
    """
    response = auth_client.get("/api/events/statistics")

    assert response.status_code != 422


def test_export_csv_route_not_shadowed_by_event_id_route(auth_client):
    """同上，針對 /api/events/export.csv。"""
    response = auth_client.get("/api/events/export.csv")

    assert response.status_code != 422


def test_statistics_invalid_bucket_query_param_returns_422(auth_client):
    response = auth_client.get("/api/events/statistics?bucket=quarter")

    assert response.status_code == 422


def test_statistics_service_value_error_returns_400_not_500(auth_client, mocker):
    mocker.patch(
        "app.api.events.stats_service.get_statistics",
        side_effect=ValueError("非法時區"),
    )

    response = auth_client.get("/api/events/statistics?tz=Bad/Zone")

    assert response.status_code == 400


@pytest.mark.parametrize(
    ("path", "service_path", "return_value"),
    [
        (
            "/api/events/statistics",
            "app.api.events.stats_service.get_statistics",
            _make_stats_response(),
        ),
        (
            "/api/events/export.csv",
            "app.api.events.stats_service.build_export_rows",
            [["title"]],
        ),
    ],
    ids=["statistics", "export"],
)
@pytest.mark.parametrize("filter_name", ["date_from", "date_to"])
def test_statistics_and_export_datetime_filters_require_an_explicit_utc_offset(
    auth_client, mocker, path, service_path, return_value, filter_name
):
    service = mocker.patch(service_path, return_value=return_value)

    aware_response = auth_client.get(
        path,
        params={filter_name: "2026-08-06T00:00:00+08:00"},
    )

    assert aware_response.status_code == 200
    parsed_filter = service.call_args.kwargs[filter_name]
    assert parsed_filter.utcoffset() == timedelta(hours=8)

    service.reset_mock()
    naive_response = auth_client.get(
        path,
        params={filter_name: "2026-08-06T00:00:00"},
    )

    assert naive_response.status_code == 422
    service.assert_not_called()


def test_export_csv_success_content_type_and_bom(auth_client, mocker):
    mocker.patch(
        "app.api.events.stats_service.build_export_rows",
        return_value=[["title", "disaster_type"], ["火警案例", "fire"]],
    )

    response = auth_client.get("/api/events/export.csv")

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert response.content.startswith(b"\xef\xbb\xbf")


def test_export_csv_content_disposition_has_ascii_and_utf8_filename(auth_client, mocker):
    mocker.patch(
        "app.api.events.stats_service.build_export_rows",
        return_value=[["title", "disaster_type"], ["火警案例", "fire"]],
    )

    response = auth_client.get("/api/events/export.csv")

    disposition = response.headers.get("content-disposition", "")
    assert "filename=" in disposition
    assert "filename*=UTF-8''" in disposition
    # Starlette 用 latin-1 編碼 header 值；中文檔名若直接塞進 filename= 會在此丟例外，
    # 進而讓整個回應變成 500。header 值必須是可 latin-1 編碼的 ASCII-safe 內容。
    disposition.encode("latin-1")


def _decoded_csv_rows(response):
    return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))


def test_export_csv_exactly_limit_rows_is_not_truncated(auth_client, mocker):
    mocker.patch(
        "app.api.events.stats_service.build_export_rows",
        return_value=[["title"], ["first"], ["second"]],
    )

    response = auth_client.get("/api/events/export.csv?limit=2")

    assert response.status_code == 200
    assert response.headers["X-Truncated"] == "false"
    assert _decoded_csv_rows(response) == [["title"], ["first"], ["second"]]


def test_export_csv_more_than_limit_is_truncated_and_emits_only_limit_rows(
    auth_client, mocker
):
    """The service may return one look-ahead row so the endpoint can detect overflow."""
    mocker.patch(
        "app.api.events.stats_service.build_export_rows",
        return_value=[["title"], ["first"], ["second"], ["look-ahead"]],
    )

    response = auth_client.get("/api/events/export.csv?limit=2")

    assert response.status_code == 200
    assert response.headers["X-Truncated"] == "true"
    assert response.headers["X-Total-Rows"] == "2"
    assert _decoded_csv_rows(response) == [["title"], ["first"], ["second"]]


def test_export_csv_limit_above_10000_is_rejected_before_query(auth_client, mocker):
    build_rows = mocker.patch(
        "app.api.events.stats_service.build_export_rows",
        return_value=[["title"]],
    )

    response = auth_client.get("/api/events/export.csv?limit=10001")

    assert response.status_code == 422
    build_rows.assert_not_called()


def test_resolution_method_note_describes_latest_not_first_resolution():
    note = _make_stats_response().resolution.method_note

    assert "最近一次" in note
    assert "首次" not in note


# 無 token 存取 /api/events/statistics 與 /api/events/export.csv 的 401 測試
# 放在 tests/test_protected_endpoints.py（沿用該檔既有慣例與風格）。

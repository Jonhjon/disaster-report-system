"""通報事件統計與 CSV 匯出。

篩選條件與 event_service.get_events 共用 apply_event_filters，
確保「統計頁看到的數字」與「災情列表看到的清單」永遠是同一組資料。
"""
import functools
import zoneinfo
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import Date, and_, case, cast, func
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import literal_column
from geoalchemy2.functions import ST_X, ST_Y

from app.models.disaster_event import DisasterEvent
from app.schemas.statistics import (
    CategoryCount,
    CrossTabCell,
    ResolutionStats,
    StatisticsResponse,
    StatisticsSummary,
    TrendPoint,
)
from app.services.event_service import apply_event_filters

Bucket = Literal["day", "week", "month"]

# 趨勢分桶數上限，避免「日分桶 + 十年區間」產生 3650 個資料點
MAX_TREND_BUCKETS = 400

_ALLOWED_BUCKETS = ("day", "week", "month")

_EXPORT_SORT_COLUMNS = {
    "occurred_at": DisasterEvent.occurred_at,
    "severity": DisasterEvent.severity,
    "report_count": DisasterEvent.report_count,
    "created_at": DisasterEvent.created_at,
}

# 匯出 CSV 用的中文標籤。與前端 types/index.ts 的 DISASTER_TYPE_LABELS /
# STATUS_LABELS 對應；未知代碼一律原樣輸出，不吞掉資料。
_DISASTER_TYPE_NAMES = {
    "trapped": "人員受困",
    "road_collapse": "路段崩塌",
    "flooding": "淹水",
    "landslide": "土石流",
    "small_landslide": "小型土石流",
    "building_damage": "建物受損",
    "utility_damage": "管線/電力受損",
    "fire": "火警",
    "other": "其他",
}

_STATUS_NAMES = {
    "reported": "通報中",
    "in_progress": "處理中",
    "resolved": "已結案",
}

_EXPORT_HEADER = [
    "事件ID",
    "標題",
    "災害類型代碼",
    "災害類型",
    "嚴重度",
    "狀態代碼",
    "狀態",
    "地點",
    "緯度",
    "經度",
    "發生時間(當地)",
    "死亡",
    "受傷",
    "其中重傷",
    "受困",
    "通報次數",
    "地點為推估",
    "時間為推估",
    "建立時間(當地)",
    "結案時間(當地)",
]


@functools.lru_cache(maxsize=1)
def _known_timezones() -> frozenset[str]:
    return frozenset(zoneinfo.available_timezones())


def validate_timezone(tz: str) -> str:
    """驗證時區字串，回傳原值。

    非法時區若直接進 SQL，Postgres 會丟 InvalidParameterValue 造成 500；
    先在此攔截並轉成 ValueError，由 API 層轉 400。

    這同時也是把時區字面值內嵌進 SQL 的前提：分桶表達式需要讓時區以
    literal 形式出現（bind parameter 無法在 date_trunc 外層被最佳化，
    也讓產生的 SQL 難以閱讀），而通過 IANA 白名單比對後的值不含任何
    可用於注入的字元。

    Raises:
        ValueError: tz 不是有效的 IANA 時區名稱。
    """
    if tz not in _known_timezones():
        raise ValueError(f"未知的時區：{tz}")
    return tz


def _validate_bucket(bucket: str) -> str:
    if bucket not in _ALLOWED_BUCKETS:
        raise ValueError(f"未知的分桶單位：{bucket}")
    return bucket


def seconds_to_hours(value: float | None) -> float | None:
    """秒轉小時（小數 1 位）。None 原樣回傳，不可 coalesce 成 0.0。"""
    if value is None:
        return None
    return round(float(value) / 3600.0, 1)


def compute_percentages(rows: list[tuple[str, int]]) -> list[CategoryCount]:
    """把 (key, count) 列表轉成含百分比的 CategoryCount 列表。

    百分比以 count 總和為分母，四捨五入到小數 1 位。
    總和為 0（或空輸入）時回傳空列表，不可丟 ZeroDivisionError。
    """
    total = sum(count for _, count in rows)
    if total <= 0:
        return []
    return [
        CategoryCount(
            key=key,
            count=count,
            percentage=round(count * 100.0 / total, 1),
        )
        for key, count in rows
    ]


def _align_bucket_start(value: date, bucket: str) -> date:
    """把任意日期對齊到所屬分桶的起點（與 Postgres date_trunc 一致）。"""
    if bucket == "week":
        return value - timedelta(days=value.weekday())  # ISO：週一起算
    if bucket == "month":
        return value.replace(day=1)
    return value


def _next_bucket(value: date, bucket: str) -> date:
    if bucket == "week":
        return value + timedelta(days=7)
    if bucket == "month":
        # 手動年月進位：12 月的下一個桶是隔年 1 月
        if value.month == 12:
            return date(value.year + 1, 1, 1)
        return value.replace(month=value.month + 1, day=1)
    return value + timedelta(days=1)


def fill_trend_gaps(
    rows: list[tuple[date, int]],
    bucket: Bucket,
    start: date | None = None,
    end: date | None = None,
    max_buckets: int = MAX_TREND_BUCKETS,
) -> list[TrendPoint]:
    """把稀疏的分桶結果補成連續序列。

    SQL 只會回傳有資料的桶。若直接畫成折線，中間的空白日期會被壓縮掉，
    時間軸尺度失真——這是圖表最常見的失真方式，必須在後端補齊。

    Args:
        rows: (桶起始當地日期, 件數)，順序不拘。
        bucket: day 步進 1 天；week 步進 7 天（起點先對齊到該週週一）；
            month 手動年月進位。
        start: 序列起點；None 時取 rows 的最小日期。
        end: 序列終點；None 時取 rows 的最大日期。
        max_buckets: 桶數上限。

    Returns:
        依 bucket_start 遞增排序的完整序列。rows 為空且未指定 start/end 時回傳
        空列表（讓前端顯示空狀態），而不是一整排 0。

    Raises:
        ValueError: 產生的桶數超過 max_buckets。
    """
    _validate_bucket(bucket)

    counts: dict[date, int] = {}
    for bucket_start, count in rows:
        aligned = _align_bucket_start(bucket_start, bucket)
        counts[aligned] = counts.get(aligned, 0) + count

    candidates_start = [start] if start is not None else []
    candidates_end = [end] if end is not None else []
    if counts:
        candidates_start.append(min(counts))
        candidates_end.append(max(counts))

    if not candidates_start or not candidates_end:
        return []

    cursor = _align_bucket_start(min(candidates_start), bucket)
    last = _align_bucket_start(max(candidates_end), bucket)

    points: list[TrendPoint] = []
    while cursor <= last:
        if len(points) >= max_buckets:
            raise ValueError(
                f"時間範圍過大（超過 {max_buckets} 個分桶），請縮小查詢區間或改用較大的分桶單位"
            )
        points.append(TrendPoint(bucket_start=cursor, count=counts.get(cursor, 0)))
        cursor = _next_bucket(cursor, bucket)

    return points


def _base_query(db: Session, filters: dict):
    """建立套好篩選的基礎查詢。每個聚合各建一條，避免互相污染。"""
    return apply_event_filters(db.query(DisasterEvent), **filters)


def _local_bucket_expr(bucket: str, tz: str):
    """當地時區的分桶表達式。

    occurred_at 是 timestamptz（內部為 UTC）。若直接 date_trunc，會以 UTC 午夜
    切桶，使台灣時間每天 08:00 之前的事件全部掉到前一天——這是系統性偏移。
    先 AT TIME ZONE 轉成當地牆鐘時間再 date_trunc 才正確。

    tz 與 bucket 皆已通過白名單驗證，內嵌為 literal 無注入風險。
    """
    local_ts = func.timezone(literal_column(f"'{tz}'"), DisasterEvent.occurred_at)
    return cast(func.date_trunc(literal_column(f"'{bucket}'"), local_ts), Date)


def _to_local_date(value: datetime | None, tz: str) -> date | None:
    if value is None:
        return None
    aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return aware.astimezone(zoneinfo.ZoneInfo(tz)).date()


def get_statistics(
    db: Session,
    *,
    search: str | None = None,
    disaster_type: str | None = None,
    severity_min: int | None = None,
    severity_max: int | None = None,
    status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    bucket: Bucket = "day",
    tz: str = "Asia/Taipei",
) -> StatisticsResponse:
    """彙總符合篩選條件的事件統計。

    時間分桶必須先把 occurred_at（timestamptz，內部 UTC）轉成 tz 的當地時間
    再 date_trunc，否則會以 UTC 午夜切桶，使台灣時間早上 08:00 之前的事件
    全部掉到前一天。

    Raises:
        ValueError: tz 非法，或趨勢桶數超過上限。
    """
    # 驗證必須在碰 DB 之前，否則非法值會變成 Postgres 的 500
    validate_timezone(tz)
    _validate_bucket(bucket)

    filters = {
        "search": search,
        "disaster_type": disaster_type,
        "severity_min": severity_min,
        "severity_max": severity_max,
        "status": status,
        "date_from": date_from,
        "date_to": date_to,
        "date_to_exclusive": True,
    }

    summary = _query_summary(db, filters)
    by_disaster_type = _query_category(db, filters, DisasterEvent.disaster_type)
    by_severity = _query_category(db, filters, DisasterEvent.severity)
    by_status = _query_category(db, filters, DisasterEvent.status)
    cross_tab = _query_cross_tab(db, filters)
    resolution = _query_resolution(db, filters)
    # 趨勢查詢刻意放最後：它是唯一帶有時區與分桶單位的查詢
    trend = _query_trend(db, filters, bucket, tz, date_from, date_to)

    return StatisticsResponse(
        summary=summary,
        by_disaster_type=by_disaster_type,
        by_severity=by_severity,
        by_status=by_status,
        trend=trend,
        cross_tab=cross_tab,
        resolution=resolution,
        bucket=bucket,
        timezone=tz,
        generated_at=datetime.now(timezone.utc),
    )


def _as_int(value) -> int:
    return int(value) if value is not None else 0


def _query_summary(db: Session, filters: dict) -> StatisticsSummary:
    row = _base_query(db, filters).with_entities(
        func.count(DisasterEvent.id),
        func.coalesce(func.sum(DisasterEvent.report_count), 0),
        func.coalesce(func.sum(DisasterEvent.casualties), 0),
        func.coalesce(func.sum(DisasterEvent.injured), 0),
        func.coalesce(func.sum(DisasterEvent.severe_injured), 0),
        func.coalesce(func.sum(DisasterEvent.trapped), 0),
        func.avg(DisasterEvent.severity),
        func.count(case((DisasterEvent.severity >= 4, 1))),
        func.count(case((DisasterEvent.status != "resolved", 1))),
    ).one()

    avg_severity = row[6]
    return StatisticsSummary(
        total_events=_as_int(row[0]),
        total_report_count=_as_int(row[1]),
        total_casualties=_as_int(row[2]),
        total_injured=_as_int(row[3]),
        total_severe_injured=_as_int(row[4]),
        total_trapped=_as_int(row[5]),
        avg_severity=(
            round(float(avg_severity), 2) if avg_severity is not None else None
        ),
        high_severity_count=_as_int(row[7]),
        unresolved_count=_as_int(row[8]),
    )


def _query_category(db: Session, filters: dict, column) -> list[CategoryCount]:
    rows = (
        _base_query(db, filters)
        .with_entities(column, func.count(DisasterEvent.id))
        .group_by(column)
        .order_by(column)
        .all()
    )
    # key 一律轉字串：severity 是整數欄位，但回應契約統一用 str
    return compute_percentages([(str(key), _as_int(count)) for key, count in rows])


def _query_cross_tab(db: Session, filters: dict) -> list[CrossTabCell]:
    rows = (
        _base_query(db, filters)
        .with_entities(
            DisasterEvent.disaster_type,
            DisasterEvent.severity,
            func.count(DisasterEvent.id),
        )
        .group_by(DisasterEvent.disaster_type, DisasterEvent.severity)
        .all()
    )
    return [
        CrossTabCell(disaster_type=str(dt), severity=int(sev), count=_as_int(count))
        for dt, sev, count in rows
    ]


def _query_resolution(db: Session, filters: dict) -> ResolutionStats:
    """結案耗時統計。

    刻意用 CASE 而非額外的 .filter()：篩選條件必須與其他聚合完全一致，
    多加 filter 會讓「這份統計的母體」在不同區塊間悄悄不同。
    """
    delta = func.extract(
        "epoch", DisasterEvent.resolved_at - DisasterEvent.created_at
    )
    measurable = and_(
        DisasterEvent.status == "resolved",
        DisasterEvent.resolved_at.isnot(None),
        DisasterEvent.resolved_at > DisasterEvent.created_at,
    )
    legacy = and_(
        DisasterEvent.status == "resolved",
        DisasterEvent.resolved_at.is_(None),
    )
    measurable_delta = case((measurable, delta))

    row = _base_query(db, filters).with_entities(
        func.count(case((measurable, 1))),
        func.count(case((legacy, 1))),
        func.avg(measurable_delta),
        # 依序集合聚合會自動忽略 NULL，因此 CASE 未命中的列不會影響分位數
        func.percentile_cont(0.5).within_group(measurable_delta.asc()),
        func.percentile_cont(0.9).within_group(measurable_delta.asc()),
    ).one()

    return ResolutionStats(
        resolved_count=_as_int(row[0]),
        legacy_excluded_count=_as_int(row[1]),
        avg_hours=seconds_to_hours(row[2]),
        median_hours=seconds_to_hours(row[3]),
        p90_hours=seconds_to_hours(row[4]),
    )


def _query_trend(
    db: Session,
    filters: dict,
    bucket: str,
    tz: str,
    date_from: datetime | None,
    date_to: datetime | None,
) -> list[TrendPoint]:
    bucket_expr = _local_bucket_expr(bucket, tz)
    rows = (
        _base_query(db, filters)
        .with_entities(bucket_expr, func.count(DisasterEvent.id))
        .group_by(bucket_expr)
        .order_by(bucket_expr)
        .all()
    )
    return fill_trend_gaps(
        [(bucket_start, _as_int(count)) for bucket_start, count in rows],
        bucket,  # type: ignore[arg-type]
        start=_to_local_date(date_from, tz),
        end=(
            _to_local_date(date_to - timedelta(microseconds=1), tz)
            if date_to is not None
            else None
        ),
    )


def _format_local(value: datetime | None, tz: str) -> str:
    """轉當地時間並輸出 Excel 認得的日期格式（不帶 T / Z）。"""
    if value is None:
        return ""
    aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return aware.astimezone(zoneinfo.ZoneInfo(tz)).strftime("%Y-%m-%d %H:%M:%S")


def _sanitize_spreadsheet_text(value: str | None) -> str:
    """Neutralize text that spreadsheet programs could interpret as a formula."""
    if not value:
        return ""
    # 只略過一般空白，保留 tab/CR/LF 本身作為危險前綴判斷依據。
    candidate = value.lstrip(" ")
    dangerous = candidate.startswith(("=", "+", "-", "@", "\t", "\r", "\n"))
    return f"'{value}" if dangerous else value


def build_export_rows(
    db: Session,
    *,
    search: str | None = None,
    disaster_type: str | None = None,
    severity_min: int | None = None,
    severity_max: int | None = None,
    status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort_by: str = "occurred_at",
    sort_order: str = "desc",
    limit: int = 10000,
    tz: str = "Asia/Taipei",
) -> list[list[str]]:
    """組出事件明細 CSV 的所有列，第 0 列為標頭。

    時間欄一律轉成 tz 當地時間並輸出 "YYYY-MM-DD HH:MM:SS"（不帶 T/Z），
    Excel 才會辨識成日期而非文字。

    Raises:
        ValueError: tz 非法。
    """
    validate_timezone(tz)

    query = apply_event_filters(
        db.query(
            DisasterEvent,
            ST_Y(DisasterEvent.location).label("lat"),
            ST_X(DisasterEvent.location).label("lng"),
        ),
        search=search,
        disaster_type=disaster_type,
        severity_min=severity_min,
        severity_max=severity_max,
        status=status,
        date_from=date_from,
        date_to=date_to,
        date_to_exclusive=True,
    )

    sort_col = _EXPORT_SORT_COLUMNS.get(sort_by, DisasterEvent.occurred_at)
    query = query.order_by(
        sort_col.asc() if sort_order == "asc" else sort_col.desc(),
        DisasterEvent.id.asc(),
    )

    rows: list[list[str]] = [list(_EXPORT_HEADER)]
    for event, lat, lng in query.limit(limit).all():
        rows.append(
            [
                str(event.id),
                _sanitize_spreadsheet_text(event.title),
                _sanitize_spreadsheet_text(event.disaster_type),
                _sanitize_spreadsheet_text(
                    _DISASTER_TYPE_NAMES.get(event.disaster_type, event.disaster_type or "")
                ),
                str(event.severity),
                _sanitize_spreadsheet_text(event.status),
                _sanitize_spreadsheet_text(
                    _STATUS_NAMES.get(event.status, event.status or "")
                ),
                _sanitize_spreadsheet_text(event.location_text),
                "" if lat is None else f"{lat:.6f}",
                "" if lng is None else f"{lng:.6f}",
                _format_local(event.occurred_at, tz),
                str(_as_int(event.casualties)),
                str(_as_int(event.injured)),
                str(_as_int(event.severe_injured)),
                str(_as_int(event.trapped)),
                str(_as_int(event.report_count)),
                "是" if event.location_approximate else "否",
                "是" if event.occurred_at_approximate else "否",
                _format_local(event.created_at, tz),
                _format_local(event.resolved_at, tz),
            ]
        )
    return rows

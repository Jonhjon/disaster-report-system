"""通報事件統計 API 的回應 schema。

沿用專案既有慣例：無統一 envelope、命名 XxxResponse、直接 import 本模組
（app/schemas/__init__.py 維持空白）。此處全是輸出 DTO、不從 ORM 物件轉換，
故不需要 model_config = {"from_attributes": True}。
"""
from datetime import date, datetime

from pydantic import BaseModel

# 結案時間指標的資料來源說明。由後端提供、UI 與匯出 CSV 原樣顯示，
# 確保口徑只有一份，不會前後端漂移。
RESOLUTION_METHOD_NOTE = (
    "結案耗時 = 事件建立時間 → 狀態最近一次轉為「已結案」的時間（resolved_at）。"
    "系統自 resolved_at 欄位上線後才開始記錄，先前既有的已結案事件無此時戳，"
    "不納入計算並另計於 legacy_excluded_count。"
    "結案後又被改回處理中的事件，其結案時戳會被清除，以最新一次結案為準。"
)


class CategoryCount(BaseModel):
    """單一分組維度的計數。

    key 對 disaster_type / status 為字串碼；對 severity 為 "1".."5"。
    刻意用 str 而非 Enum：資料庫對 disaster_type 沒有 CheckConstraint，
    可能存在 LLM 枚舉清單以外的值，用 Enum 會讓整個回應驗證失敗。
    """

    key: str
    count: int
    percentage: float  # 0-100，四捨五入到小數 1 位


class TrendPoint(BaseModel):
    """時間趨勢的單一分桶。

    bucket_start 刻意用 date 而非 datetime：桶起點是「使用者時區的當地日期」，
    用 datetime 序列化會帶上時區，前端 new Date() 會再位移一次而錯位。
    """

    bucket_start: date
    count: int


class CrossTabCell(BaseModel):
    """災害類型 × 嚴重度交叉表的單一格。

    稀疏表示：沒有事件的組合不會出現在回應中，由前端補 0。
    """

    disaster_type: str
    severity: int
    count: int


class ResolutionStats(BaseModel):
    """處理效率統計。"""

    resolved_count: int  # 納入計算的樣本數（分母，必須揭露）
    legacy_excluded_count: int  # 已結案但無 resolved_at 的舊資料筆數
    avg_hours: float | None  # 無樣本時為 None，不是 0.0
    median_hours: float | None
    p90_hours: float | None
    method_note: str = RESOLUTION_METHOD_NOTE


class StatisticsSummary(BaseModel):
    """總覽數字卡。"""

    total_events: int
    # SUM(report_count)：累計通報次數。與 disaster_reports 資料表的列數不相等
    # （merge 時是累加、刪除事件會把 report.event_id 設為 NULL 產生孤兒通報）。
    total_report_count: int
    total_casualties: int
    total_injured: int
    total_severe_injured: int
    total_trapped: int
    avg_severity: float | None
    high_severity_count: int  # severity >= 4
    unresolved_count: int  # status != 'resolved'


class StatisticsResponse(BaseModel):
    summary: StatisticsSummary
    by_disaster_type: list[CategoryCount]
    by_severity: list[CategoryCount]
    by_status: list[CategoryCount]
    trend: list[TrendPoint]
    cross_tab: list[CrossTabCell]
    resolution: ResolutionStats
    bucket: str  # day | week | month
    timezone: str
    time_field: str = "occurred_at"  # 明示分桶依據，避免讀者誤解為建立時間
    generated_at: datetime

"""DisasterEvent model 結構性契約測試。"""

from __future__ import annotations

from app.models.disaster_event import DisasterEvent


def test_occurred_at_is_not_nullable():
    """occurred_at 必須為非空，確保應用層可放心省略 None 檢查。"""
    column = DisasterEvent.__table__.columns["occurred_at"]
    assert column.nullable is False, (
        "occurred_at 必須 nullable=False；若要放寬，請同步更新 app/api/chat.py 的合併邏輯"
    )


def test_location_text_is_not_nullable():
    """location_text 非空是 dedup / 顯示的前提。"""
    column = DisasterEvent.__table__.columns["location_text"]
    assert column.nullable is False


def test_severity_is_not_nullable():
    column = DisasterEvent.__table__.columns["severity"]
    assert column.nullable is False


def test_occurred_at_approximate_defaults_false():
    """新事件預設 occurred_at_approximate=False；只有 LLM 未取得時間時才為 True。"""
    column = DisasterEvent.__table__.columns["occurred_at_approximate"]
    assert column.default.arg is False


def test_occurred_at_approximate_not_nullable():
    """欄位需 nullable=False，避免前端遇到 null 需額外處理。"""
    column = DisasterEvent.__table__.columns["occurred_at_approximate"]
    assert column.nullable is False

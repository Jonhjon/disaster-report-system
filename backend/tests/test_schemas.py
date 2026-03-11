"""
方向一：Pydantic Schema 驗證（5 案例）
"""
import pytest
from pydantic import ValidationError

from app.schemas.chat import ChatRequest
from app.schemas.event import EventUpdate


# Case 1: EventUpdate severity 超出範圍（0 和 6）
@pytest.mark.parametrize("severity", [0, 6])
def test_event_update_severity_out_of_range(severity):
    with pytest.raises(ValidationError):
        EventUpdate(severity=severity)


# Case 2: EventUpdate status 非法值
def test_event_update_status_invalid():
    with pytest.raises(ValidationError):
        EventUpdate(status="deleted")


# Case 3: ChatRequest 不傳 message → ValidationError
def test_chat_request_missing_message():
    with pytest.raises(ValidationError):
        ChatRequest()


# Case 4: ChatRequest 合法資料，history 預設為 []
def test_chat_request_valid_history_default():
    req = ChatRequest(message="台北市發生地震")
    assert req.message == "台北市發生地震"
    assert req.history == []


# Case 5: EventUpdate 所有欄位均為 None（全選填）→ 通過
def test_event_update_all_none():
    update = EventUpdate()
    assert update.title is None
    assert update.severity is None
    assert update.description is None
    assert update.status is None
    assert update.casualties is None
    assert update.injured is None
    assert update.trapped is None

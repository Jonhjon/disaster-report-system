"""驗證行動 App 的 verified_phone 整合。

涵蓋：
- ChatRequest schema 接受 verified_phone 與 device_location（可選）
- _apply_verified_phone() helper 覆寫 reporter_phone
- _stream_kwargs() helper 對應傳給 llm_service.stream_chat 的關鍵字
- llm_service._build_system_prompt() 在有 verified_phone 時注入指示
"""
from __future__ import annotations

import inspect

import pytest

from app.api.chat import _apply_verified_phone, _stream_kwargs
from app.schemas.chat import ChatRequest, DeviceLocation
from app.schemas.llm_tools import SubmitDisasterReportPayload
from app.services import llm_service


def _payload(**overrides) -> SubmitDisasterReportPayload:
    data = {
        "disaster_type": "fire",
        "description": "建物起火",
        "location_text": "台北市信義區市府路45號",
        "severity": 3,
        "casualties": 0,
        "injured": 0,
        "trapped": 0,
        "reporter_name": "張小明",
        "reporter_phone": "0000000000",  # LLM 從對話擷取（不可信）
    }
    data.update(overrides)
    return SubmitDisasterReportPayload.model_validate(data)


# ---------------------------------------------------------------------------
# ChatRequest schema
# ---------------------------------------------------------------------------


def test_chat_request_accepts_verified_phone_and_location():
    req = ChatRequest(
        message="火警",
        verified_phone="+886912345678",
        device_location={"lat": 25.033, "lng": 121.565, "accuracy_m": 12.0},
    )
    assert req.verified_phone == "+886912345678"
    assert req.device_location is not None
    assert req.device_location.lat == 25.033
    assert req.device_location.lng == 121.565
    assert req.device_location.accuracy_m == 12.0


def test_chat_request_verified_phone_optional():
    """既有網頁端不傳 verified_phone 仍可建立 ChatRequest。"""
    req = ChatRequest(message="火警")
    assert req.verified_phone is None
    assert req.device_location is None


def test_chat_request_invalid_location_rejected():
    with pytest.raises(Exception):
        ChatRequest(
            message="火警",
            device_location={"lat": 999.0, "lng": 0.0},
        )


# ---------------------------------------------------------------------------
# _apply_verified_phone helper
# ---------------------------------------------------------------------------


def test_apply_verified_phone_overrides_reporter_phone():
    payload = _payload(reporter_phone="0000000000")
    result = _apply_verified_phone(payload, "+886912345678")
    assert result.reporter_phone == "+886912345678"
    assert result.reporter_name == payload.reporter_name  # 其他欄位不變
    assert result.disaster_type == payload.disaster_type


def test_apply_verified_phone_none_keeps_original():
    payload = _payload(reporter_phone="0912345678")
    result = _apply_verified_phone(payload, None)
    assert result.reporter_phone == "0912345678"
    # 原 payload 也不變動（model_copy 應為純函式）
    assert payload.reporter_phone == "0912345678"


def test_apply_verified_phone_empty_string_keeps_original():
    payload = _payload(reporter_phone="0912345678")
    result = _apply_verified_phone(payload, "")
    assert result.reporter_phone == "0912345678"


# ---------------------------------------------------------------------------
# _stream_kwargs helper
# ---------------------------------------------------------------------------


def test_stream_kwargs_without_extras():
    req = ChatRequest(message="火警")
    kwargs = _stream_kwargs(req)
    assert kwargs == {
        "verified_phone": None,
        "device_location": None,
        "temperature": None,
    }


def test_stream_kwargs_with_phone_and_location():
    req = ChatRequest(
        message="火警",
        verified_phone="+886912345678",
        device_location={"lat": 25.033, "lng": 121.565},
    )
    kwargs = _stream_kwargs(req)
    assert kwargs["verified_phone"] == "+886912345678"
    assert kwargs["device_location"] == {
        "lat": 25.033,
        "lng": 121.565,
        "accuracy_m": None,
    }


# ---------------------------------------------------------------------------
# llm_service system prompt
# ---------------------------------------------------------------------------


def test_build_system_prompt_no_extras():
    prompt = llm_service._build_system_prompt()
    assert "當前時間" in prompt
    assert "已驗證電話" not in prompt
    assert "裝置 GPS 位置" not in prompt


def test_build_system_prompt_injects_verified_phone():
    prompt = llm_service._build_system_prompt(verified_phone="+886912345678")
    assert "已驗證電話" in prompt
    assert "+886912345678" in prompt
    assert "不要再向使用者詢問電話" in prompt


def test_build_system_prompt_injects_device_location():
    prompt = llm_service._build_system_prompt(
        device_location={"lat": 25.033, "lng": 121.565}
    )
    assert "裝置 GPS 位置" in prompt
    assert "25.033" in prompt
    assert "121.565" in prompt


def test_stream_chat_accepts_kwargs():
    """stream_chat 函式簽章需有 verified_phone / device_location 兩個關鍵字參數。"""
    sig = inspect.signature(llm_service.stream_chat)
    assert "verified_phone" in sig.parameters
    assert "device_location" in sig.parameters
    assert sig.parameters["verified_phone"].kind == inspect.Parameter.KEYWORD_ONLY
    assert sig.parameters["device_location"].kind == inspect.Parameter.KEYWORD_ONLY


# ---------------------------------------------------------------------------
# DeviceLocation schema
# ---------------------------------------------------------------------------


def test_device_location_validation():
    loc = DeviceLocation(lat=25.0, lng=121.5)
    assert loc.lat == 25.0
    assert loc.lng == 121.5
    assert loc.accuracy_m is None


def test_device_location_rejects_out_of_range():
    with pytest.raises(Exception):
        DeviceLocation(lat=-91.0, lng=0.0)
    with pytest.raises(Exception):
        DeviceLocation(lat=0.0, lng=181.0)

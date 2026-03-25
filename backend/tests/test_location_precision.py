"""
地點精確度完整單元測試

Section A: _location_is_precise (10 既有 + 15 新增 = 25 cases)
Section B: _location_hint        (12 既有 + 12 新增 = 24 cases)
Section C: event_generator 追問流程整合測試 (8 cases)

執行：
    cd backend && python -m pytest tests/test_location_precision.py -v
"""
import json
import pytest
from unittest.mock import AsyncMock, patch

from app.api.chat import _location_hint, _location_is_precise


# ---------------------------------------------------------------------------
# SSE 事件迴圈隔離：sse_starlette 的 AppStatus.should_exit_event 在測試間
# 共享，會被第一個測試建立的 event loop 所綁定，導致後續測試失敗。
# 每個測試前重置為 None 讓 sse_starlette 在下次請求時重新建立。
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_sse_app_status():
    from sse_starlette.sse import AppStatus
    AppStatus.should_exit_event = None
    yield
    AppStatus.should_exit_event = None


# ---------------------------------------------------------------------------
# 共用座標常數
# ---------------------------------------------------------------------------

_GOOGLE_PLACES_COORDS = {
    "source": "google_places",
    "latitude": 23.5,
    "longitude": 121.0,
    "display_name": "test",
}

_NOMINATIM_COORDS = {
    "source": "nominatim",
    "latitude": 23.9,
    "longitude": 121.5,
    "display_name": "test",
}


# ---------------------------------------------------------------------------
# Section A: _location_is_precise — 25 cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,coords,expected", [
    # ── 既有 case（對應 test_location_hint.py）── #

    # 完整（縣市 + 路 + 號）→ 精確
    ("花蓮縣吉安鄉慶北三街123號",    None,                  True),
    ("台北市信義區市府路45號",        None,                  True),
    ("新北市板橋區中山路一段100號",   None,                  True),

    # Google Places 找到具體商家 → 精確（即使沒門牌）
    ("花蓮縣吉安鄉慶北三街7-ELEVEN", _GOOGLE_PLACES_COORDS, True),
    ("台北市信義區某商店",            _GOOGLE_PLACES_COORDS, True),

    # 缺門牌且非 Google Places → 不精確
    ("花蓮縣吉安鄉慶北三街",         None,                  False),
    ("花蓮縣吉安鄉慶北三街",         _NOMINATIM_COORDS,     False),

    # 缺縣市
    ("吉安慶北三街123號",             None,                  False),

    # 缺路名
    ("花蓮縣123號",                   None,                  False),

    # 空字串
    ("",                              None,                  False),

    # ── 新增邊界 case ── #

    # 1. 「市」出現在商業名稱中（好市多），但仍無路名+號 → False
    ("好市多中和店",                  None,                  False),

    # 2. 「道」出現在學校名中（道明），無縣市+號 → False
    ("道明國中附近",                  None,                  False),

    # 3. 有縣市，「道」被計入路名（道明），但無「號」→ False
    ("台北市道明國中附近",            None,                  False),

    # 4. 合法「路」名 + 號 → True
    ("台北市忠孝東路四段1號",         None,                  True),

    # 5. 「大道」算路名 → True
    ("台北市中山大道123號",           None,                  True),

    # 6. 巷弄完整（含弄） → True
    ("台北市和平東路二段3巷5弄2號",   None,                  True),

    # 7. source="google"（非 google_places）→ False
    ("某地點", {"source": "google", "latitude": 25.0, "longitude": 121.0},     False),

    # 8. source="tgos" → False
    ("某地點", {"source": "tgos",   "latitude": 25.0, "longitude": 121.0},     False),

    # 9. source="nominatim" → False（和既有 case 7 等價，但 text 不同）
    ("另一地點", {"source": "nominatim", "latitude": 25.0, "longitude": 121.0}, False),

    # 10. coords={} 無 source 欄位 → False
    ("某地點", {},                                                               False),

    # 11. 有座標但無 source 鍵 → False
    ("某地點", {"latitude": 25.0, "longitude": 121.0},                          False),

    # 12. 場所後綴（教室）+ google_places → True
    ("三育基督學院教室",              _GOOGLE_PLACES_COORDS,                    True),

    # 13. 有縣市+號但無路名 → False
    ("台北市123號",                   None,                  False),

    # 14. 有路+號但無縣市 → False
    ("中正路123號",                   None,                  False),

    # 15. 有縣市+路但無號 → False
    ("花蓮縣中正路",                  None,                  False),
])
def test_location_is_precise(text, coords, expected):
    result = _location_is_precise(text, coords)
    assert result == expected, (
        f"text={text!r}, source={coords and coords.get('source')!r} → "
        f"期望 {expected}，實際 {result}"
    )


# ---------------------------------------------------------------------------
# Section B: _location_hint — 24 cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("location_text,expected_keyword", [
    # ── 既有 case（對應 test_location_hint.py）── #

    # 缺縣市 → 詢問縣市
    ("建安街12巷5號",               "縣市"),
    ("中正路附近",                   "縣市"),
    ("7-11旁邊",                     "縣市"),
    ("學校門口",                      "縣市"),

    # 有縣市但缺路名 → 詢問路名
    ("花蓮縣",                       "路名"),
    ("台北市信義區",                  "路名"),
    ("新北市板橋區某處",              "路名"),

    # 有縣市+路名但缺門牌 → 詢問門牌
    ("台北市中正路",                  "門牌"),
    ("花蓮縣中央路三段",              "門牌"),
    ("新竹市光復路二段",              "門牌"),

    # 完整地址（縣市+路+號）→ 通用提示
    ("台北市信義區市府路1號",         "具體"),
    ("花蓮縣花蓮市中央路三段808號",   "具體"),

    # ── 新增邊界 case ── #

    # 1. 「好市多」含「市」→ 誤判為有縣市，因此詢問路名（已知誤判行為）
    ("好市多",                        "路名"),

    # 2. 「台北市101」有「市」但缺路名 → 詢問路名
    ("台北市101",                     "路名"),

    # 3. 有縣+「大道」但缺號 → 詢問門牌
    ("花蓮縣中山大道",                "門牌"),

    # 4. 有縣市+巷但缺號 → 詢問門牌
    ("台北市和平東路三段2巷",         "門牌"),

    # 5. 有縣市+弄但缺號 → 詢問門牌
    ("台北市和平東路三段2巷5弄",      "門牌"),

    # 6. 空字串 → 詢問縣市
    ("",                              "縣市"),

    # 7. 完全無地點資訊 → 詢問縣市
    ("附近發生火災",                   "縣市"),

    # 8. 有縣+鄉但缺路 → 詢問路名
    ("花蓮縣吉安鄉",                  "路名"),

    # 9. 捷運地標，無縣市 → 詢問縣市
    ("捷運忠孝復興站",                "縣市"),

    # 10. 完整地址 → 通用提示
    ("台北市信義路五段7號",           "具體"),

    # 11. 完整含區 → 通用提示
    ("新北市新店區安坑路100號",       "具體"),

    # 12. 「大道路」包含「道」與「路」→ 完整地址，通用提示
    ("台北市大道路1號",               "具體"),
])
def test_location_hint(location_text, expected_keyword):
    hint = _location_hint(location_text)
    assert expected_keyword in hint, (
        f"location_text={location_text!r} → hint={hint!r}，期望包含 {expected_keyword!r}"
    )


# ---------------------------------------------------------------------------
# Section C: event_generator 追問流程整合測試 — 8 cases
#
# 策略：
#   - 使用 conftest.py 的 `client` fixture（已注入 mock_db）
#   - patch llm_service.stream_chat / geocode_address / _process_tool_use
#   - 以 HTTP POST /api/chat 觸發 SSE，解析回傳事件
# ---------------------------------------------------------------------------

_BASE_TOOL_DATA = {
    "disaster_type": "flooding",
    "location_text": "某個地方",          # 不精確
    "severity": 2,
    "description": "附近淹水",
    "casualties": 0,
    "injured": 0,
    "trapped": 0,
}

_PRECISE_TOOL_DATA = {
    **_BASE_TOOL_DATA,
    "location_text": "台北市信義路45號",  # 精確（縣市+路+號）
}

_FAKE_PROCESS_RESULT = {
    "status": "created",
    "event_id": "fake-event-id",
    "message": "已建立新的災情事件「台北市某處淹水」",
    "geocoded_address": None,
}

_NOMINATIM_RESULT = {
    "source": "nominatim",
    "latitude": 25.033,
    "longitude": 121.565,
    "display_name": "台北市信義路",
}

_GOOGLE_PLACES_RESULT = {
    "source": "google_places",
    "latitude": 25.033,
    "longitude": 121.565,
    "display_name": "某商店",
}


def _parse_sse(response_text: str) -> list[dict]:
    """Parse SSE 回應文字，回傳所有 data: 行的 JSON 物件列表。"""
    events = []
    for line in response_text.splitlines():
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except (json.JSONDecodeError, ValueError):
                pass
    return events


def _make_stream(*chunks):
    """建立一個每次呼叫都回傳新 async generator 的函式。"""
    async def _gen(_messages):
        for chunk in chunks:
            yield chunk
    return _gen


def _sequential_streams(*stream_factories):
    """按呼叫順序依序回傳不同的 async generator（用於多輪 LLM 呼叫模擬）。"""
    call_idx = {"n": 0}

    def _dispatch(messages):
        idx = call_idx["n"]
        call_idx["n"] += 1
        if idx < len(stream_factories):
            return stream_factories[idx](messages)
        # 若超出預期呼叫次數，回傳空串流
        async def _empty(_):
            yield {"type": "done"}
        return _empty(messages)

    return _dispatch


# ── C-1: geocoding 失敗 → 追問縣市，無 report_submitted ─────────────────────

def test_geocoding_fails_triggers_followup(client):
    """geocoding 回傳 None → 觸發 continuation，輸出追問文字，不含 report_submitted。"""
    dispatch = _sequential_streams(
        _make_stream(
            {"type": "tool_use", "data": _BASE_TOOL_DATA, "tool_use_id": "tu_001"},
            {"type": "done"},
        ),
        _make_stream(
            {"type": "text", "content": "請問您在哪個縣市？"},
            {"type": "done"},
        ),
    )

    with patch("app.api.chat.geocode_address", new=AsyncMock(return_value=None)), \
         patch("app.api.chat.llm_service.stream_chat", side_effect=dispatch):
        response = client.post("/api/chat", json={"message": "附近淹水了", "history": []})

    events = _parse_sse(response.text)
    event_types = [e.get("type") for e in events]

    assert "report_submitted" not in event_types, "geocoding 失敗時不應直接建立通報"
    text_contents = [e.get("content", "") for e in events if e.get("type") == "text"]
    assert any(text_contents), "應有追問文字被輸出"


# ── C-2: geocoding 成功但不精確 → 追問路名，無 report_submitted ──────────────

def test_geocoding_imprecise_triggers_followup(client):
    """geocoding 成功（非 google_places）但地址不精確 → 觸發 continuation，輸出追問。"""
    imprecise_tool_data = {**_BASE_TOOL_DATA, "location_text": "花蓮縣"}  # 有縣無路

    dispatch = _sequential_streams(
        _make_stream(
            {"type": "tool_use", "data": imprecise_tool_data, "tool_use_id": "tu_002"},
            {"type": "done"},
        ),
        _make_stream(
            {"type": "text", "content": "請問附近的路名是？"},
            {"type": "done"},
        ),
    )

    with patch("app.api.chat.geocode_address", new=AsyncMock(return_value=_NOMINATIM_RESULT)), \
         patch("app.api.chat.llm_service.stream_chat", side_effect=dispatch):
        response = client.post("/api/chat", json={"message": "花蓮有土石流", "history": []})

    events = _parse_sse(response.text)
    event_types = [e.get("type") for e in events]

    assert "report_submitted" not in event_types, "地址不精確時不應直接建立通報"
    text_contents = [e.get("content", "") for e in events if e.get("type") == "text"]
    assert any(text_contents), "應有追問文字被輸出"


# ── C-3: geocoding 成功且精確 → 直接建立，含 report_submitted ───────────────

def test_geocoding_precise_creates_report(client):
    """geocoding 回傳 google_places → _location_is_precise=True → 直接建立通報。"""
    dispatch = _make_stream(
        {"type": "tool_use", "data": _BASE_TOOL_DATA, "tool_use_id": "tu_003"},
        {"type": "done"},
    )

    with patch("app.api.chat.geocode_address", new=AsyncMock(return_value=_GOOGLE_PLACES_RESULT)), \
         patch("app.api.chat.llm_service.stream_chat", side_effect=dispatch), \
         patch("app.api.chat._process_tool_use", new=AsyncMock(return_value=_FAKE_PROCESS_RESULT)):
        response = client.post("/api/chat", json={"message": "某商店附近淹水", "history": []})

    events = _parse_sse(response.text)
    submitted = [e for e in events if e.get("type") == "report_submitted"]

    assert len(submitted) == 1, "精確地址應建立一筆通報"
    assert submitted[0].get("status") == "created"


# ── C-4: continuation 中 Claude 再次呼叫工具 → 強制建立 ─────────────────────

def test_continuation_tool_use_force_creates(client):
    """continuation 裡 LLM 再次呼叫 submit_disaster_report → 強制接受並建立通報。"""
    dispatch = _sequential_streams(
        # 第 1 次：geocoding 失敗，進入 continuation
        _make_stream(
            {"type": "tool_use", "data": _BASE_TOOL_DATA, "tool_use_id": "tu_004a"},
            {"type": "done"},
        ),
        # 第 2 次（continuation）：LLM 提交精確地址
        _make_stream(
            {"type": "tool_use", "data": _PRECISE_TOOL_DATA, "tool_use_id": "tu_004b"},
            {"type": "done"},
        ),
    )

    with patch("app.api.chat.geocode_address", new=AsyncMock(return_value=None)), \
         patch("app.api.chat.llm_service.stream_chat", side_effect=dispatch), \
         patch("app.api.chat._process_tool_use", new=AsyncMock(return_value=_FAKE_PROCESS_RESULT)):
        response = client.post("/api/chat", json={"message": "台北市信義路45號淹水", "history": []})

    events = _parse_sse(response.text)
    submitted = [e for e in events if e.get("type") == "report_submitted"]

    assert len(submitted) == 1, "continuation 中再次呼叫工具應強制建立通報"


# ── C-5: MAX_GEOCODING_RETRIES 常數 = 3 ─────────────────────────────────────

def test_max_geocoding_retries_constant():
    """MAX_GEOCODING_RETRIES 應為 3，對應計劃文件規格。"""
    from app.api.chat import MAX_GEOCODING_RETRIES
    assert MAX_GEOCODING_RETRIES == 3


# ── C-6: failed_attempts 計算：API 歷史訊息（string content）不觸發計數 ───────

def test_failed_attempts_string_history_not_counted(client):
    """
    ChatMessage.content 為 str，無法觸發 failed_attempts 計數器。
    即使歷史訊息內文包含「geocoding 失敗」字樣，counter 仍為 0，
    因為計數邏輯要求 isinstance(content, list)。
    因此 geocoding 失敗時仍會觸發追問（非強制建立）。
    """
    history_with_text = [
        {"role": "user", "content": "geocoding 失敗"},
        {"role": "assistant", "content": "geocoding 失敗"},
        {"role": "user", "content": "geocoding 失敗"},
    ]

    dispatch = _sequential_streams(
        _make_stream(
            {"type": "tool_use", "data": _BASE_TOOL_DATA, "tool_use_id": "tu_006"},
            {"type": "done"},
        ),
        _make_stream(
            {"type": "text", "content": "請問您在哪個縣市？"},
            {"type": "done"},
        ),
    )

    with patch("app.api.chat.geocode_address", new=AsyncMock(return_value=None)), \
         patch("app.api.chat.llm_service.stream_chat", side_effect=dispatch):
        response = client.post("/api/chat", json={
            "message": "還是一樣地方淹水",
            "history": history_with_text,
        })

    events = _parse_sse(response.text)
    event_types = [e.get("type") for e in events]

    # 因 failed_attempts=0（string content 不計），仍觸發追問而非強制建立
    assert "report_submitted" not in event_types, \
        "string content 歷史不應觸發 failed_attempts，應仍走追問流程"


# ── C-7: 追問理由依失敗類型不同 ──────────────────────────────────────────────

def test_followup_reason_differs_by_failure_type(client):
    """
    geocoding 失敗 → continuation message 包含「geocoding 失敗」。
    地址不精確 → continuation message 包含「地址不夠精確」。
    """
    captured_messages = []

    def capturing_dispatch(messages):
        captured_messages.append(messages)
        if len(captured_messages) == 1:
            return _make_stream(
                {"type": "tool_use", "data": _BASE_TOOL_DATA, "tool_use_id": "tu_007"},
                {"type": "done"},
            )(messages)
        return _make_stream(
            {"type": "text", "content": "請問縣市？"},
            {"type": "done"},
        )(messages)

    # Case A: geocoding 失敗
    captured_messages.clear()
    with patch("app.api.chat.geocode_address", new=AsyncMock(return_value=None)), \
         patch("app.api.chat.llm_service.stream_chat", side_effect=capturing_dispatch):
        client.post("/api/chat", json={"message": "淹水", "history": []})

    assert len(captured_messages) >= 2, "應至少有兩次 stream_chat 呼叫"
    continuation_content = _extract_tool_result_content(captured_messages[1])
    assert "geocoding 失敗" in continuation_content, \
        f"geocoding 失敗時 reason 應包含「geocoding 失敗」，實際：{continuation_content!r}"

    # Case B: geocoding 成功但不精確
    captured_messages.clear()
    imprecise_data = {**_BASE_TOOL_DATA, "location_text": "花蓮縣"}

    def capturing_dispatch_imprecise(messages):
        captured_messages.append(messages)
        if len(captured_messages) == 1:
            return _make_stream(
                {"type": "tool_use", "data": imprecise_data, "tool_use_id": "tu_007b"},
                {"type": "done"},
            )(messages)
        return _make_stream(
            {"type": "text", "content": "請問路名？"},
            {"type": "done"},
        )(messages)

    with patch("app.api.chat.geocode_address", new=AsyncMock(return_value=_NOMINATIM_RESULT)), \
         patch("app.api.chat.llm_service.stream_chat", side_effect=capturing_dispatch_imprecise):
        client.post("/api/chat", json={"message": "花蓮有事", "history": []})

    assert len(captured_messages) >= 2
    continuation_content_b = _extract_tool_result_content(captured_messages[1])
    assert "地址不夠精確" in continuation_content_b, \
        f"不精確時 reason 應包含「地址不夠精確」，實際：{continuation_content_b!r}"


def _extract_tool_result_content(messages: list) -> str:
    """從 messages 中找出最後一筆 tool_result 的 content 文字。"""
    for m in reversed(messages):
        content = m.get("content")
        if isinstance(content, list):
            for item in content:
                if item.get("type") == "tool_result":
                    return item.get("content", "")
    return ""


# ── C-8: 使用者補充縣市後重試 → continuation 工具呼叫建立通報 ────────────────

def test_user_supplements_location_creates_report(client):
    """
    第一輪：geocoding 失敗，LLM 追問。
    第二輪（continuation 中）：LLM 再次呼叫 submit_disaster_report →
    強制接受，產生 report_submitted。
    等同於 C-4，但著重驗證 event_id 是否出現於回應。
    """
    precise_data = {**_BASE_TOOL_DATA, "location_text": "台北市中正路100號"}
    fake_result = {
        "status": "created",
        "event_id": "event-supplement-test",
        "message": "已建立災情事件",
        "geocoded_address": "台北市中正路100號",
    }

    dispatch = _sequential_streams(
        _make_stream(
            {"type": "tool_use", "data": _BASE_TOOL_DATA, "tool_use_id": "tu_008a"},
            {"type": "done"},
        ),
        _make_stream(
            {"type": "tool_use", "data": precise_data, "tool_use_id": "tu_008b"},
            {"type": "done"},
        ),
    )

    with patch("app.api.chat.geocode_address", new=AsyncMock(return_value=None)), \
         patch("app.api.chat.llm_service.stream_chat", side_effect=dispatch), \
         patch("app.api.chat._process_tool_use", new=AsyncMock(return_value=fake_result)):
        response = client.post("/api/chat", json={
            "message": "台北市中正路100號附近淹水",
            "history": [],
        })

    events = _parse_sse(response.text)
    submitted = [e for e in events if e.get("type") == "report_submitted"]

    assert len(submitted) == 1
    assert submitted[0].get("event_id") == "event-supplement-test"

"""
Geocoding 服務測試
策略：Mock httpx 請求，不打真實網路
"""
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.geocoding_service import (
    _NEARBY_KEYWORDS,
    _geocode_cache,
    _geocode_address_impl,
    _extract_landmark_pattern,
    _haversine_m,
    _in_taiwan,
    _strip_place_suffix,
    geocode_address,
    geocode_google_places,
    geocode_nearby_candidates,
    geocode_nearby_search,
)


# ---------------------------------------------------------------------------
# Fixture: clear in-memory cache before each test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_cache():
    _geocode_cache.clear()
    yield
    _geocode_cache.clear()


# ---------------------------------------------------------------------------
# A. _in_taiwan — 座標範圍驗證 (12 cases)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lat,lon,expected", [
    # 台灣本島正常地點
    (25.033, 121.565, True),   # 台北市信義區
    (24.813, 120.967, True),   # 新竹市
    (23.548, 121.017, True),   # 花蓮縣
    (22.999, 120.212, True),   # 台南市
    (22.627, 120.302, True),   # 高雄市
    # 離島（邊界內）
    (24.432, 119.977, True),   # 金門縣（經度接近下限）
    (22.041, 121.548, True),   # 蘭嶼
    # 境外
    (35.689, 139.692, False),  # 東京
    (39.906, 116.391, False),  # 北京
    (1.290, 103.852, False),   # 新加坡
    (51.507, -0.127, False),   # 倫敦
    (22.302, 114.177, False),  # 香港
])
def test_in_taiwan(lat, lon, expected):
    assert _in_taiwan(lat, lon) == expected


# ---------------------------------------------------------------------------
# Original cases (updated for cache-aware behaviour)
# ---------------------------------------------------------------------------

# Case 23: 傳入「台北市信義區」→ 回傳有效座標
@pytest.mark.asyncio
async def test_geocode_valid_address():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"lat": "25.0330", "lon": "121.5654"}
    ]

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_async_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_async_client
        mock_async_client.get.return_value = mock_response

        result = await geocode_address("台北市信義區")

    assert result is not None
    assert abs(result["latitude"] - 25.033) < 0.01
    assert abs(result["longitude"] - 121.565) < 0.01


# Case 24: Nominatim 回傳空陣列（地址找不到）→ None
@pytest.mark.asyncio
async def test_geocode_address_not_found():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = []

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_async_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_async_client
        mock_async_client.get.return_value = mock_response

        result = await geocode_address("不存在的地址zzz")

    assert result is None


# ---------------------------------------------------------------------------
# B. Nominatim 座標過濾 (3 cases)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_nominatim_out_of_taiwan_filtered():
    """Nominatim 回傳台灣境外座標 → 被過濾，最終回傳 None（無 Google key）"""
    # Returns Beijing coordinates — should be rejected by _in_taiwan
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"lat": "39.9042", "lon": "116.4074"}]

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_async_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_async_client
        mock_async_client.get.return_value = mock_response
        # No Google API key → google steps return None early
        with patch("app.services.geocoding_service.settings") as mock_settings:
            mock_settings.ANTHROPIC_API_KEY = None
            mock_settings.GOOGLE_MAPS_API_KEY = None
            result = await geocode_address("建安街")

    assert result is None


@pytest.mark.asyncio
async def test_nominatim_in_taiwan_accepted():
    """Nominatim 回傳台灣境內座標 → 正常回傳"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"lat": "25.0330", "lon": "121.5654", "display_name": "台北"}]

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_async_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_async_client
        mock_async_client.get.return_value = mock_response
        with patch("app.services.geocoding_service.settings") as mock_settings:
            mock_settings.ANTHROPIC_API_KEY = None
            mock_settings.GOOGLE_MAPS_API_KEY = None
            result = await geocode_address("台北市信義區市府路")

    assert result is not None
    assert _in_taiwan(result["latitude"], result["longitude"])


@pytest.mark.asyncio
async def test_nominatim_first_out_second_in():
    """Nominatim 第一筆境外、第二筆境內 → 繼續嘗試並回傳境內結果"""
    out_response = MagicMock()
    out_response.status_code = 200
    out_response.json.return_value = [{"lat": "39.9", "lon": "116.4"}]  # Beijing

    in_response = MagicMock()
    in_response.status_code = 200
    in_response.json.return_value = [{"lat": "23.548", "lon": "121.017", "display_name": "花蓮"}]

    # First query returns outside-Taiwan, subsequent queries return Taiwan
    call_count = {"n": 0}
    async def side_effect(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return out_response
        return in_response

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_async_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_async_client
        mock_async_client.get.side_effect = side_effect
        with patch("app.services.geocoding_service.settings") as mock_settings:
            mock_settings.ANTHROPIC_API_KEY = None
            mock_settings.GOOGLE_MAPS_API_KEY = None
            result = await geocode_address("建安街12巷")

    assert result is not None
    assert _in_taiwan(result["latitude"], result["longitude"])


# ---------------------------------------------------------------------------
# C. Google Places 信心度（9 cases）
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("types,should_return", [
    # 模糊結果（應拒絕）
    (["locality", "political"], False),
    (["administrative_area_level_1", "political"], False),
    (["administrative_area_level_2", "political"], False),
    (["country", "political"], False),
    # 精確結果（應接受）
    (["establishment", "point_of_interest", "store"], True),
    (["street_address"], True),
    (["premise"], True),
    (["route"], True),
    # 混合（含 establishment，不是純模糊）
    (["locality", "establishment"], True),
])
@pytest.mark.asyncio
async def test_google_places_confidence(types, should_return):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "OK",
        "results": [{
            "types": types,
            "geometry": {"location": {"lat": 25.033, "lng": 121.565}},
            "formatted_address": "測試地址",
        }],
    }

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_async_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_async_client
        mock_async_client.get.return_value = mock_response
        with patch("app.services.geocoding_service.settings") as mock_settings:
            mock_settings.GOOGLE_MAPS_API_KEY = "fake-key"
            result = await geocode_google_places("花蓮縣")

    if should_return:
        assert result is not None
    else:
        assert result is None


# ---------------------------------------------------------------------------
# E. _strip_place_suffix 單元測試
# ---------------------------------------------------------------------------

def test_strip_place_suffix_with_suffix():
    assert _strip_place_suffix("三育基督學院教室") == "三育基督學院"
    assert _strip_place_suffix("國立台灣大學操場") == "國立台灣大學"
    assert _strip_place_suffix("台北火車站停車場") == "台北火車站"
    assert _strip_place_suffix("台大醫院大廳") == "台大醫院"
    assert _strip_place_suffix("新光三越宿舍") == "新光三越"


def test_strip_place_suffix_without_suffix():
    assert _strip_place_suffix("三育基督學院") is None
    assert _strip_place_suffix("台北車站") is None
    assert _strip_place_suffix("花蓮縣政府") is None


def test_strip_place_suffix_only_suffix():
    """剝除後核心為空字串 → 回傳 None"""
    assert _strip_place_suffix("教室") is None


# ---------------------------------------------------------------------------
# F. Named-place fast path 整合測試（Mock geocode_google_places）
# ---------------------------------------------------------------------------

_FAKE_PLACES_RESULT = {
    "latitude": 24.0,
    "longitude": 121.0,
    "display_name": "三育基督學院",
    "source": "google_places",
}


@pytest.mark.asyncio
async def test_named_place_fast_path_suffix_stripped():
    """原始查詢失敗，剝除後綴後成功 → 回傳剝除後結果"""
    async def fake_geocode_google_places(q: str):
        if q == "三育基督學院":
            return _FAKE_PLACES_RESULT
        return None

    with patch(
        "app.services.geocoding_service.geocode_google_places",
        side_effect=fake_geocode_google_places,
    ), patch(
        "app.services.geocoding_service.extract_structured_address",
        new=AsyncMock(return_value="三育基督學院教室"),
    ):
        result = await _geocode_address_impl("三育基督學院教室")

    assert result is not None
    assert result["source"] == "google_places"
    assert result["display_name"] == "三育基督學院"


@pytest.mark.asyncio
async def test_named_place_fast_path_no_suffix_no_extra_call():
    """原始查詢成功（無後綴）→ 不呼叫剝除後綴版本"""
    call_log = []

    async def fake_geocode_google_places(q: str):
        call_log.append(q)
        if q == "三育基督學院":
            return _FAKE_PLACES_RESULT
        return None

    with patch(
        "app.services.geocoding_service.geocode_google_places",
        side_effect=fake_geocode_google_places,
    ), patch(
        "app.services.geocoding_service.extract_structured_address",
        new=AsyncMock(return_value="三育基督學院"),
    ):
        result = await _geocode_address_impl("三育基督學院")

    assert result is not None
    assert result["source"] == "google_places"
    # Should only have been called once with the original query
    assert call_log == ["三育基督學院"]


@pytest.mark.asyncio
async def test_named_place_fast_path_suffix_stripped_still_fails():
    """剝除後綴後仍查無結果 → 繼續 TGOS/Nominatim fallback"""
    async def fake_geocode_google_places(q: str):
        return None

    nominatim_response = MagicMock()
    nominatim_response.status_code = 200
    nominatim_response.json.return_value = [
        {"lat": "24.0", "lon": "121.0", "display_name": "Fallback"}
    ]

    with patch(
        "app.services.geocoding_service.geocode_google_places",
        side_effect=fake_geocode_google_places,
    ), patch(
        "app.services.geocoding_service.extract_structured_address",
        new=AsyncMock(return_value="三育基督學院教室"),
    ), patch(
        "app.services.geocoding_service.geocode_tgos",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.services.geocoding_service.extract_address_components",
        new=AsyncMock(return_value={}),
    ), patch("httpx.AsyncClient") as mock_client_cls:
        mock_async_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_async_client
        mock_async_client.get.return_value = nominatim_response
        result = await _geocode_address_impl("三育基督學院教室")

    # Should fall through to Nominatim and return a result
    assert result is not None
    assert result.get("latitude") == 24.0


# ---------------------------------------------------------------------------
# D. In-memory 快取（3 cases）
# 策略：mock _geocode_address_impl 直接計算內部函式呼叫次數，
#       避免 httpx.AsyncClient 因 TGOS/Nominatim 各自開 session 而干擾計數。
# ---------------------------------------------------------------------------

_FAKE_RESULT = {"latitude": 22.999, "longitude": 120.212, "display_name": "台南"}


@pytest.mark.asyncio
async def test_geocode_cache_hit():
    """相同地址兩次呼叫 → _geocode_address_impl 只被呼叫一次"""
    with patch(
        "app.services.geocoding_service._geocode_address_impl",
        new=AsyncMock(return_value=_FAKE_RESULT),
    ) as mock_impl:
        result1 = await geocode_address("台南市中西區")
        result2 = await geocode_address("台南市中西區")

    assert result1 == _FAKE_RESULT
    assert result2 == _FAKE_RESULT
    # Second call should hit cache, not call impl again
    assert mock_impl.call_count == 1


@pytest.mark.asyncio
async def test_geocode_cache_different_addresses():
    """不同地址各自獨立快取，各呼叫一次 _geocode_address_impl"""
    with patch(
        "app.services.geocoding_service._geocode_address_impl",
        new=AsyncMock(return_value=_FAKE_RESULT),
    ) as mock_impl:
        await geocode_address("新竹市東區")
        await geocode_address("新竹縣竹北市")

    assert mock_impl.call_count == 2


@pytest.mark.asyncio
async def test_geocode_cache_no_cache_on_failure():
    """Geocoding 失敗（None）不應被快取 → 每次都呼叫 _geocode_address_impl"""
    with patch(
        "app.services.geocoding_service._geocode_address_impl",
        new=AsyncMock(return_value=None),
    ) as mock_impl:
        result1 = await geocode_address("不存在的地址abc")
        result2 = await geocode_address("不存在的地址abc")

    assert result1 is None
    assert result2 is None
    # Both calls must reach impl (None is not cached)
    assert mock_impl.call_count == 2


# ---------------------------------------------------------------------------
# G. _NEARBY_KEYWORDS regex（9 cases）
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    # 有空間關係詞 → match
    ("肯德基附近的麥當勞", True),
    ("火車站旁邊的便利商店", True),
    ("台北101對面的全家", True),
    ("學校靠近的醫院", True),
    ("公園旁的咖啡廳", True),
    ("捷運站周邊的餐廳", True),
    # 純地址/單一場所 → no match
    ("台北市信義區市府路45號", False),
    ("台大醫院", False),
    ("花蓮縣政府", False),
])
def test_nearby_keywords_regex(text, expected):
    assert bool(_NEARBY_KEYWORDS.search(text)) == expected


# ---------------------------------------------------------------------------
# H. _extract_landmark_pattern（7 cases）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extract_landmark_no_api_key():
    """無 API key → 即使有空間關係詞也回傳 None"""
    with patch("app.services.geocoding_service.settings") as mock_settings:
        mock_settings.ANTHROPIC_API_KEY = None
        result = await _extract_landmark_pattern("肯德基附近的麥當勞")
    assert result is None


@pytest.mark.asyncio
async def test_extract_landmark_no_nearby_keyword_skips_llm():
    """無空間關係詞 → regex 快速跳過，LLM 不被呼叫"""
    with patch("app.services.geocoding_service.settings") as mock_settings:
        mock_settings.ANTHROPIC_API_KEY = "fake-key"
        with patch("anthropic.AsyncAnthropic") as mock_anthropic_cls:
            result = await _extract_landmark_pattern("台大醫院")
    assert result is None
    mock_anthropic_cls.assert_not_called()


@pytest.mark.asyncio
async def test_extract_landmark_normal_parse():
    """正常解析 target/landmark，area=None"""
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text='{"target": "麥當勞", "landmark": "肯德基", "area": null}')]

    with patch("app.services.geocoding_service.settings") as mock_settings:
        mock_settings.ANTHROPIC_API_KEY = "fake-key"
        with patch("anthropic.AsyncAnthropic") as mock_anthropic_cls:
            mock_client = AsyncMock()
            mock_anthropic_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(return_value=mock_message)
            result = await _extract_landmark_pattern("肯德基附近的麥當勞")

    assert result == {"target": "麥當勞", "landmark": "肯德基", "area": None}


@pytest.mark.asyncio
async def test_extract_landmark_with_area():
    """有 area 的解析"""
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text='{"target": "麥當勞", "landmark": "肯德基", "area": "花蓮市"}')]

    with patch("app.services.geocoding_service.settings") as mock_settings:
        mock_settings.ANTHROPIC_API_KEY = "fake-key"
        with patch("anthropic.AsyncAnthropic") as mock_anthropic_cls:
            mock_client = AsyncMock()
            mock_anthropic_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(return_value=mock_message)
            result = await _extract_landmark_pattern("花蓮市肯德基附近的麥當勞")

    assert result == {"target": "麥當勞", "landmark": "肯德基", "area": "花蓮市"}


@pytest.mark.asyncio
async def test_extract_landmark_llm_returns_null():
    """LLM 回傳字串 'null' → None"""
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="null")]

    with patch("app.services.geocoding_service.settings") as mock_settings:
        mock_settings.ANTHROPIC_API_KEY = "fake-key"
        with patch("anthropic.AsyncAnthropic") as mock_anthropic_cls:
            mock_client = AsyncMock()
            mock_anthropic_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(return_value=mock_message)
            result = await _extract_landmark_pattern("公園旁的咖啡廳")

    assert result is None


@pytest.mark.asyncio
async def test_extract_landmark_llm_raises_exception():
    """LLM 拋出例外 → None"""
    with patch("app.services.geocoding_service.settings") as mock_settings:
        mock_settings.ANTHROPIC_API_KEY = "fake-key"
        with patch("anthropic.AsyncAnthropic") as mock_anthropic_cls:
            mock_client = AsyncMock()
            mock_anthropic_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(side_effect=Exception("API error"))
            result = await _extract_landmark_pattern("捷運站旁邊的藥局")

    assert result is None


@pytest.mark.asyncio
async def test_extract_landmark_llm_returns_code_block():
    """LLM 回傳 code block 格式 → 正確解析"""
    raw = '```json\n{"target": "星巴克", "landmark": "麥當勞", "area": null}\n```'
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=raw)]

    with patch("app.services.geocoding_service.settings") as mock_settings:
        mock_settings.ANTHROPIC_API_KEY = "fake-key"
        with patch("anthropic.AsyncAnthropic") as mock_anthropic_cls:
            mock_client = AsyncMock()
            mock_anthropic_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(return_value=mock_message)
            result = await _extract_landmark_pattern("麥當勞對面的星巴克")

    assert result == {"target": "星巴克", "landmark": "麥當勞", "area": None}


# ---------------------------------------------------------------------------
# I. geocode_nearby_search（6 cases）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_nearby_search_no_api_key():
    """無 API key → None"""
    with patch("app.services.geocoding_service.settings") as mock_settings:
        mock_settings.GOOGLE_MAPS_API_KEY = None
        result = await geocode_nearby_search("麥當勞", 23.97, 121.6)
    assert result is None


@pytest.mark.asyncio
async def test_nearby_search_success():
    """成功回傳台灣境內座標，source=google_nearby"""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "OK",
        "results": [{
            "types": ["restaurant", "food"],
            "geometry": {"location": {"lat": 23.975, "lng": 121.605}},
            "vicinity": "花蓮市中央路",
            "name": "麥當勞",
        }],
    }

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_async_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_async_client
        mock_async_client.get.return_value = mock_response
        with patch("app.services.geocoding_service.settings") as mock_settings:
            mock_settings.GOOGLE_MAPS_API_KEY = "fake-key"
            result = await geocode_nearby_search("麥當勞", 23.97, 121.6)

    assert result is not None
    assert result["source"] == "google_nearby"
    assert abs(result["latitude"] - 23.975) < 0.01
    assert abs(result["longitude"] - 121.605) < 0.01


@pytest.mark.asyncio
async def test_nearby_search_vague_type_returns_none():
    """結果 types 全為 VAGUE_TYPES → None"""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "OK",
        "results": [{
            "types": ["locality", "political"],
            "geometry": {"location": {"lat": 23.97, "lng": 121.6}},
            "vicinity": "花蓮市",
        }],
    }

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_async_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_async_client
        mock_async_client.get.return_value = mock_response
        with patch("app.services.geocoding_service.settings") as mock_settings:
            mock_settings.GOOGLE_MAPS_API_KEY = "fake-key"
            result = await geocode_nearby_search("花蓮市", 23.97, 121.6)

    assert result is None


@pytest.mark.asyncio
async def test_nearby_search_out_of_taiwan_returns_none():
    """回傳境外座標 → None"""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "OK",
        "results": [{
            "types": ["restaurant"],
            "geometry": {"location": {"lat": 35.689, "lng": 139.692}},
            "vicinity": "東京",
        }],
    }

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_async_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_async_client
        mock_async_client.get.return_value = mock_response
        with patch("app.services.geocoding_service.settings") as mock_settings:
            mock_settings.GOOGLE_MAPS_API_KEY = "fake-key"
            result = await geocode_nearby_search("麥當勞", 35.689, 139.692)

    assert result is None


@pytest.mark.asyncio
async def test_nearby_search_status_not_ok():
    """status != OK → None"""
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "ZERO_RESULTS", "results": []}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_async_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_async_client
        mock_async_client.get.return_value = mock_response
        with patch("app.services.geocoding_service.settings") as mock_settings:
            mock_settings.GOOGLE_MAPS_API_KEY = "fake-key"
            result = await geocode_nearby_search("麥當勞", 23.97, 121.6)

    assert result is None


@pytest.mark.asyncio
async def test_nearby_search_httpx_exception():
    """httpx 拋出例外 → None"""
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_async_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_async_client
        mock_async_client.get.side_effect = httpx.ConnectError("connection failed")
        with patch("app.services.geocoding_service.settings") as mock_settings:
            mock_settings.GOOGLE_MAPS_API_KEY = "fake-key"
            result = await geocode_nearby_search("麥當勞", 23.97, 121.6)

    assert result is None


# ---------------------------------------------------------------------------
# J. _geocode_address_impl Step 0 整合（6 cases）
# ---------------------------------------------------------------------------

_LANDMARK_RESULT = {
    "latitude": 23.970,
    "longitude": 121.600,
    "display_name": "肯德基花蓮店",
    "source": "google_places",
}

_NEARBY_CANDIDATE = {
    "name": "麥當勞花蓮店",
    "address": "花蓮市中央路",
    "latitude": 23.975,
    "longitude": 121.605,
    "distance_m": 100,
}


@pytest.mark.asyncio
async def test_step0_500m_succeeds():
    """地標找到 + 500m 成功（單一候選）→ 直接回傳 nearby 結果，無 candidates key"""
    with patch("app.services.geocoding_service.extract_structured_address",
               new=AsyncMock(return_value="肯德基附近的麥當勞")), \
         patch("app.services.geocoding_service._extract_landmark_pattern",
               new=AsyncMock(return_value={"target": "麥當勞", "landmark": "肯德基", "area": None})), \
         patch("app.services.geocoding_service.geocode_google_places",
               new=AsyncMock(return_value=_LANDMARK_RESULT)), \
         patch("app.services.geocoding_service.geocode_nearby_candidates",
               new=AsyncMock(return_value=[_NEARBY_CANDIDATE])):
        result = await _geocode_address_impl("肯德基附近的麥當勞")

    assert result is not None
    assert result["source"] == "google_nearby"
    assert "candidates" not in result


@pytest.mark.asyncio
async def test_step0_500m_fails_1500m_succeeds():
    """500m 失敗 + 1500m 成功 → geocode_nearby_candidates 被呼叫兩次"""
    call_radii = []

    async def fake_nearby(keyword, lat, lon, radius):
        call_radii.append(radius)
        if radius == 500:
            return []
        return [_NEARBY_CANDIDATE]

    with patch("app.services.geocoding_service.extract_structured_address",
               new=AsyncMock(return_value="肯德基附近的麥當勞")), \
         patch("app.services.geocoding_service._extract_landmark_pattern",
               new=AsyncMock(return_value={"target": "麥當勞", "landmark": "肯德基", "area": None})), \
         patch("app.services.geocoding_service.geocode_google_places",
               new=AsyncMock(return_value=_LANDMARK_RESULT)), \
         patch("app.services.geocoding_service.geocode_nearby_candidates",
               side_effect=fake_nearby):
        result = await _geocode_address_impl("肯德基附近的麥當勞")

    assert result is not None
    assert result["source"] == "google_nearby"
    assert call_radii == [500, 1500]


@pytest.mark.asyncio
async def test_step0_landmark_not_found_no_nearby_search():
    """地標 geocode_google_places 回傳 None → geocode_nearby_candidates 不被呼叫"""
    mock_nearby = AsyncMock()

    with patch("app.services.geocoding_service.extract_structured_address",
               new=AsyncMock(return_value="肯德基附近的麥當勞")), \
         patch("app.services.geocoding_service._extract_landmark_pattern",
               new=AsyncMock(return_value={"target": "麥當勞", "landmark": "肯德基", "area": None})), \
         patch("app.services.geocoding_service.geocode_google_places",
               new=AsyncMock(return_value=None)), \
         patch("app.services.geocoding_service.geocode_nearby_candidates", mock_nearby), \
         patch("app.services.geocoding_service.extract_address_components",
               new=AsyncMock(return_value={})), \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_async_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_async_client
        mock_async_client.get.return_value = MagicMock(
            status_code=200, json=MagicMock(return_value=[])
        )
        await _geocode_address_impl("肯德基附近的麥當勞")

    mock_nearby.assert_not_called()


@pytest.mark.asyncio
async def test_step0_both_radii_fail_fallback():
    """500m + 1500m 都失敗 → geocode_nearby_candidates 呼叫兩次，後續 fallback 繼續"""
    call_radii = []

    async def fake_nearby(keyword, lat, lon, radius):
        call_radii.append(radius)
        return []

    with patch("app.services.geocoding_service.extract_structured_address",
               new=AsyncMock(return_value="肯德基附近的麥當勞")), \
         patch("app.services.geocoding_service._extract_landmark_pattern",
               new=AsyncMock(return_value={"target": "麥當勞", "landmark": "肯德基", "area": None})), \
         patch("app.services.geocoding_service.geocode_google_places",
               new=AsyncMock(return_value=_LANDMARK_RESULT)), \
         patch("app.services.geocoding_service.geocode_nearby_candidates",
               side_effect=fake_nearby), \
         patch("app.services.geocoding_service.extract_address_components",
               new=AsyncMock(return_value={})), \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_async_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_async_client
        mock_async_client.get.return_value = MagicMock(
            status_code=200, json=MagicMock(return_value=[])
        )
        result = await _geocode_address_impl("肯德基附近的麥當勞")

    # 確認兩次 radius 都嘗試了
    assert call_radii == [500, 1500]
    # 結果不是來自 google_nearby（Step 0 已失敗，由後續 fallback 產生）
    assert result is None or result.get("source") != "google_nearby"


@pytest.mark.asyncio
async def test_step0_skipped_for_plain_address():
    """純地址（_extract_landmark_pattern 回傳 None）→ geocode_nearby_candidates 不被呼叫"""
    mock_nearby = AsyncMock()

    nominatim_response = MagicMock()
    nominatim_response.status_code = 200
    nominatim_response.json.return_value = [
        {"lat": "25.033", "lon": "121.565", "display_name": "台北市信義區"}
    ]

    with patch("app.services.geocoding_service.extract_structured_address",
               new=AsyncMock(return_value="台北市信義區市府路45號")), \
         patch("app.services.geocoding_service._extract_landmark_pattern",
               new=AsyncMock(return_value=None)), \
         patch("app.services.geocoding_service.geocode_nearby_candidates", mock_nearby), \
         patch("app.services.geocoding_service.extract_address_components",
               new=AsyncMock(return_value={})), \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_async_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_async_client
        mock_async_client.get.return_value = nominatim_response
        result = await _geocode_address_impl("台北市信義區市府路45號")

    mock_nearby.assert_not_called()
    assert result is not None


@pytest.mark.asyncio
async def test_step0_area_prefix_in_queries():
    """有 area 時，地標查詢與目標查詢都加上 area 前綴"""
    places_calls = []

    async def fake_places(q: str):
        places_calls.append(q)
        if "肯德基" in q:
            return _LANDMARK_RESULT
        return None

    nearby_calls = []

    async def fake_nearby(keyword, lat, lon, radius):
        nearby_calls.append(keyword)
        return [_NEARBY_CANDIDATE]

    with patch("app.services.geocoding_service.extract_structured_address",
               new=AsyncMock(return_value="花蓮市肯德基附近的麥當勞")), \
         patch("app.services.geocoding_service._extract_landmark_pattern",
               new=AsyncMock(return_value={"target": "麥當勞", "landmark": "肯德基", "area": "花蓮市"})), \
         patch("app.services.geocoding_service.geocode_google_places",
               side_effect=fake_places), \
         patch("app.services.geocoding_service.geocode_nearby_candidates",
               side_effect=fake_nearby):
        result = await _geocode_address_impl("花蓮市肯德基附近的麥當勞")

    assert result is not None
    # 第一個 places 呼叫應包含 area + landmark
    assert any("花蓮市" in q and "肯德基" in q for q in places_calls), f"places_calls={places_calls}"
    # nearby 查詢應包含 area + target
    assert any("花蓮市" in k and "麥當勞" in k for k in nearby_calls), f"nearby_calls={nearby_calls}"


# ---------------------------------------------------------------------------
# K. geocode_nearby_candidates（5 cases）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_nearby_candidates_no_api_key():
    """無 API key → 空列表"""
    with patch("app.services.geocoding_service.settings") as mock_settings:
        mock_settings.GOOGLE_MAPS_API_KEY = None
        result = await geocode_nearby_candidates("公園", 23.97, 121.6)
    assert result == []


@pytest.mark.asyncio
async def test_nearby_candidates_sorted_by_distance():
    """多筆結果按距離排序（近的在前），過濾 VAGUE_TYPES"""
    # 兩個公園，第二筆距離更近
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "OK",
        "results": [
            {
                "name": "南埔公園",
                "types": ["park", "point_of_interest"],
                "geometry": {"location": {"lat": 23.980, "lng": 121.610}},
                "vicinity": "花蓮市南埔路",
            },
            {
                "name": "知卡宣森林公園",
                "types": ["park", "point_of_interest"],
                "geometry": {"location": {"lat": 23.971, "lng": 121.601}},
                "vicinity": "花蓮市知卡宣路",
            },
        ],
    }

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_async_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_async_client
        mock_async_client.get.return_value = mock_response
        with patch("app.services.geocoding_service.settings") as mock_settings:
            mock_settings.GOOGLE_MAPS_API_KEY = "fake-key"
            # landmark 在 23.970, 121.600
            result = await geocode_nearby_candidates("公園", 23.970, 121.600)

    assert len(result) == 2
    # 知卡宣更近（距離約 156m），南埔更遠（距離約 1.1km）
    assert result[0]["name"] == "知卡宣森林公園"
    assert result[1]["name"] == "南埔公園"
    assert result[0]["distance_m"] < result[1]["distance_m"]


@pytest.mark.asyncio
async def test_nearby_candidates_filters_vague_types():
    """VAGUE_TYPES 的結果被過濾掉"""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "OK",
        "results": [
            {
                "name": "花蓮市",
                "types": ["locality", "political"],
                "geometry": {"location": {"lat": 23.97, "lng": 121.6}},
                "vicinity": "花蓮市",
            },
            {
                "name": "知卡宣森林公園",
                "types": ["park", "point_of_interest"],
                "geometry": {"location": {"lat": 23.971, "lng": 121.601}},
                "vicinity": "花蓮市知卡宣路",
            },
        ],
    }

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_async_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_async_client
        mock_async_client.get.return_value = mock_response
        with patch("app.services.geocoding_service.settings") as mock_settings:
            mock_settings.GOOGLE_MAPS_API_KEY = "fake-key"
            result = await geocode_nearby_candidates("公園", 23.970, 121.600)

    assert len(result) == 1
    assert result[0]["name"] == "知卡宣森林公園"


@pytest.mark.asyncio
async def test_nearby_candidates_zero_results():
    """ZERO_RESULTS → 空列表"""
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "ZERO_RESULTS", "results": []}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_async_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_async_client
        mock_async_client.get.return_value = mock_response
        with patch("app.services.geocoding_service.settings") as mock_settings:
            mock_settings.GOOGLE_MAPS_API_KEY = "fake-key"
            result = await geocode_nearby_candidates("公園", 23.97, 121.6)

    assert result == []


@pytest.mark.asyncio
async def test_nearby_candidates_limit_enforced():
    """結果超過 limit → 只回傳前 limit 筆（按距離）"""
    mock_response = MagicMock()
    # 產生 6 筆結果
    mock_response.json.return_value = {
        "status": "OK",
        "results": [
            {
                "name": f"公園{i}",
                "types": ["park"],
                "geometry": {"location": {"lat": 23.970 + i * 0.001, "lng": 121.600}},
                "vicinity": f"花蓮市路{i}",
            }
            for i in range(6)
        ],
    }

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_async_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_async_client
        mock_async_client.get.return_value = mock_response
        with patch("app.services.geocoding_service.settings") as mock_settings:
            mock_settings.GOOGLE_MAPS_API_KEY = "fake-key"
            result = await geocode_nearby_candidates("公園", 23.970, 121.600, limit=4)

    assert len(result) == 4


# ---------------------------------------------------------------------------
# L. Step 0 多候選消歧義（3 cases）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_step0_multiple_candidates_adds_candidates_key():
    """多個候選 → result 包含 candidates key，長度為 2"""
    candidate_a = {
        "name": "知卡宣森林公園",
        "address": "花蓮市知卡宣路",
        "latitude": 23.971,
        "longitude": 121.601,
        "distance_m": 120,
    }
    candidate_b = {
        "name": "南埔公園",
        "address": "花蓮市南埔路",
        "latitude": 23.980,
        "longitude": 121.610,
        "distance_m": 350,
    }

    with patch("app.services.geocoding_service.extract_structured_address",
               new=AsyncMock(return_value="南埔營區旁邊的公園")), \
         patch("app.services.geocoding_service._extract_landmark_pattern",
               new=AsyncMock(return_value={"target": "公園", "landmark": "南埔營區", "area": None})), \
         patch("app.services.geocoding_service.geocode_google_places",
               new=AsyncMock(return_value=_LANDMARK_RESULT)), \
         patch("app.services.geocoding_service.geocode_nearby_candidates",
               new=AsyncMock(return_value=[candidate_a, candidate_b])):
        result = await _geocode_address_impl("南埔營區旁邊的公園")

    assert result is not None
    assert result["source"] == "google_nearby"
    assert "candidates" in result
    assert len(result["candidates"]) == 2
    # 第一筆為最近的（知卡宣）
    assert result["candidates"][0]["name"] == "知卡宣森林公園"
    assert result["latitude"] == candidate_a["latitude"]


@pytest.mark.asyncio
async def test_step0_single_candidate_no_candidates_key():
    """單一候選 → result 不包含 candidates key"""
    with patch("app.services.geocoding_service.extract_structured_address",
               new=AsyncMock(return_value="南埔營區旁邊的公園")), \
         patch("app.services.geocoding_service._extract_landmark_pattern",
               new=AsyncMock(return_value={"target": "公園", "landmark": "南埔營區", "area": None})), \
         patch("app.services.geocoding_service.geocode_google_places",
               new=AsyncMock(return_value=_LANDMARK_RESULT)), \
         patch("app.services.geocoding_service.geocode_nearby_candidates",
               new=AsyncMock(return_value=[_NEARBY_CANDIDATE])):
        result = await _geocode_address_impl("南埔營區旁邊的公園")

    assert result is not None
    assert "candidates" not in result


@pytest.mark.asyncio
async def test_step0_closest_is_used_as_result_coordinates():
    """多候選時，result 座標為第一筆（最近的）候選座標"""
    closest = {
        "name": "知卡宣森林公園",
        "address": "花蓮市知卡宣路",
        "latitude": 23.971,
        "longitude": 121.601,
        "distance_m": 120,
    }
    farther = {
        "name": "南埔公園",
        "address": "花蓮市南埔路",
        "latitude": 23.980,
        "longitude": 121.610,
        "distance_m": 350,
    }

    with patch("app.services.geocoding_service.extract_structured_address",
               new=AsyncMock(return_value="南埔營區旁邊的公園")), \
         patch("app.services.geocoding_service._extract_landmark_pattern",
               new=AsyncMock(return_value={"target": "公園", "landmark": "南埔營區", "area": None})), \
         patch("app.services.geocoding_service.geocode_google_places",
               new=AsyncMock(return_value=_LANDMARK_RESULT)), \
         patch("app.services.geocoding_service.geocode_nearby_candidates",
               new=AsyncMock(return_value=[closest, farther])):
        result = await _geocode_address_impl("南埔營區旁邊的公園")

    assert result["latitude"] == closest["latitude"]
    assert result["longitude"] == closest["longitude"]


# ---------------------------------------------------------------------------
# M. _haversine_m 單元測試（2 cases）
# ---------------------------------------------------------------------------

def test_haversine_same_point():
    """同一點距離為 0"""
    assert _haversine_m(23.97, 121.6, 23.97, 121.6) == 0.0


def test_haversine_known_distance():
    """台北→花蓮約 120km"""
    dist = _haversine_m(25.033, 121.565, 23.975, 121.605)
    assert 115_000 < dist < 125_000

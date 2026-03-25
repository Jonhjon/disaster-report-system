"""
Geocoding 服務測試
策略：Mock httpx 請求，不打真實網路
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.geocoding_service import (
    _geocode_cache,
    _geocode_address_impl,
    _in_taiwan,
    _strip_place_suffix,
    geocode_address,
    geocode_google_places,
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

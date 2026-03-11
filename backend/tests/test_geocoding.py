"""
方向五：Geocoding 服務（2 案例）
策略：Mock httpx 請求，不打真實網路
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.geocoding_service import geocode_address


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

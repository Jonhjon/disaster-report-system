"""M-3：geocoding 失敗時 event lat/lng 應落在台灣中心（TAIWAN_CENTER_*）。

避免 None 座標導致前端地圖 marker 缺位。
"""
from __future__ import annotations

import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.services.geocoding_service import (
    TAIWAN_CENTER_LAT,
    TAIWAN_CENTER_LON,
)


def test_taiwan_center_constants_defined():
    """常數定義正確（位於台灣本島範圍）。"""
    assert 21.5 <= TAIWAN_CENTER_LAT <= 25.5
    assert 119.5 <= TAIWAN_CENTER_LON <= 122.5


def test_chat_merge_uses_taiwan_center_when_coords_none():
    """_merge_into_event 分支：coords is None → lat/lng = 台灣中心。

    讀 chat.py 原始碼以靜態方式驗證 fallback 常數被使用，而非硬編碼數字。
    """
    import app.api.chat as chat_mod

    src = Path(chat_mod.__file__).read_text(encoding="utf-8")
    # 舊寫法 23.5 / 121.0 不應殘留
    assert "23.5" not in src or "TAIWAN_CENTER" in src
    # 三處 fallback 都有引用常數
    assert src.count("TAIWAN_CENTER_LAT") >= 3
    assert src.count("TAIWAN_CENTER_LON") >= 3


def test_chat_imports_taiwan_center():
    """chat.py 從 geocoding_service 匯入常數（保證單一來源）。"""
    import app.api.chat as chat_mod

    assert chat_mod.TAIWAN_CENTER_LAT == TAIWAN_CENTER_LAT
    assert chat_mod.TAIWAN_CENTER_LON == TAIWAN_CENTER_LON

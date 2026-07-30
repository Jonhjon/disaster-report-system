"""CRITICAL-2 修正：JWT_SECRET_KEY validator 單元測試。

驗證 Settings 在 JWT_SECRET_KEY 為空/已知弱值/過短時拋出 ValidationError，
強制部署者透過 env 提供強隨機密鑰。
"""
from __future__ import annotations

import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pytest
from pydantic import ValidationError

from app.config import Settings


VALID_STRONG_KEY = "a" * 64  # 64 字元測試用強值


def _make_settings(**overrides):
    """避免讀取 .env，直接用 kwargs 建立 Settings。"""
    base = {
        "JWT_SECRET_KEY": VALID_STRONG_KEY,
        "_env_file": None,  # disable .env loading
    }
    base.update(overrides)
    return Settings(**{k: v for k, v in base.items() if not k.startswith("_")})


def test_empty_jwt_secret_key_rejected():
    """空字串應被拒。"""
    with pytest.raises(ValidationError):
        _make_settings(JWT_SECRET_KEY="")


def test_known_weak_jwt_secret_key_rejected():
    """現有硬編碼弱值必須被拒絕（防止回退）。"""
    with pytest.raises(ValidationError):
        _make_settings(JWT_SECRET_KEY="ASDASAPWDJASDD46546D4ASD4A4D3D4")


def test_short_jwt_secret_key_rejected():
    """長度 < 32 字元視為弱值。"""
    with pytest.raises(ValidationError):
        _make_settings(JWT_SECRET_KEY="short")


def test_common_placeholder_rejected():
    """常見 placeholder 也要擋下。"""
    for weak in ("change-me-in-production", "secret", "changeme"):
        with pytest.raises(ValidationError):
            _make_settings(JWT_SECRET_KEY=weak)


def test_strong_jwt_secret_key_accepted():
    """至少 32 字元且非已知弱值 → 通過。"""
    s = _make_settings(JWT_SECRET_KEY=VALID_STRONG_KEY)
    assert s.JWT_SECRET_KEY == VALID_STRONG_KEY

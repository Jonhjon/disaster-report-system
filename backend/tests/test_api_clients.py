"""統一 Anthropic API client factory 單元測試（TDD）。

驗證 `app.services.api_clients` 提供 lazy-init singleton，且會依
`settings.ANTHROPIC_BASE_URL` 組裝 AsyncAnthropic。
"""
from __future__ import annotations

import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pytest


@pytest.fixture(autouse=True)
def _reset_client():
    """每個測試跑完都清掉 singleton，避免互相污染。"""
    from app.services.api_clients import reset_anthropic_client

    reset_anthropic_client()
    yield
    reset_anthropic_client()


def test_returns_singleton():
    """兩次呼叫必回同一個實例。"""
    from app.services.api_clients import get_anthropic_client

    c1 = get_anthropic_client()
    c2 = get_anthropic_client()
    assert c1 is c2


def test_uses_configured_base_url(monkeypatch):
    """monkeypatch ANTHROPIC_BASE_URL → client.base_url 反映設定值。"""
    from app.services import api_clients
    from app.services.api_clients import get_anthropic_client

    monkeypatch.setattr(api_clients.settings, "ANTHROPIC_BASE_URL", "https://custom.example")
    api_clients.reset_anthropic_client()

    client = get_anthropic_client()
    assert str(client.base_url).rstrip("/") == "https://custom.example"


def test_empty_base_url_falls_back_to_official():
    """ANTHROPIC_BASE_URL 為空字串時 → 使用 Anthropic SDK 預設（api.anthropic.com）。"""
    from app.services import api_clients
    from app.services.api_clients import get_anthropic_client

    original = api_clients.settings.ANTHROPIC_BASE_URL
    api_clients.settings.ANTHROPIC_BASE_URL = ""
    api_clients.reset_anthropic_client()
    try:
        client = get_anthropic_client()
        # SDK 預設 base_url 含 "anthropic.com"
        assert "anthropic.com" in str(client.base_url)
    finally:
        api_clients.settings.ANTHROPIC_BASE_URL = original
        api_clients.reset_anthropic_client()


def test_reset_creates_new_instance():
    """reset_anthropic_client() 之後取得新實例與舊實例不同。"""
    from app.services.api_clients import (
        get_anthropic_client,
        reset_anthropic_client,
    )

    c1 = get_anthropic_client()
    reset_anthropic_client()
    c2 = get_anthropic_client()
    assert c1 is not c2

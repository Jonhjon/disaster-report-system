"""統一管理外部 API client。目前僅 Anthropic。

設計原則：
- Lazy-init singleton：首次呼叫才建立實例，多 request 共用同一個 httpx connection pool。
- 透過 `settings.ANTHROPIC_BASE_URL` 控制 base_url，空字串表示走 Anthropic 官方端點。
- 測試用 `reset_anthropic_client()` 清空 singleton，避免 env var monkeypatch 無效。
"""
from __future__ import annotations

import anthropic

from app.config import settings

_anthropic_client: anthropic.AsyncAnthropic | None = None


def get_anthropic_client() -> anthropic.AsyncAnthropic:
    """取得共享的 AsyncAnthropic 實例（lazy-init singleton）。"""
    global _anthropic_client
    if _anthropic_client is None:
        kwargs: dict = {"api_key": settings.ANTHROPIC_API_KEY}
        if settings.ANTHROPIC_BASE_URL:
            kwargs["base_url"] = settings.ANTHROPIC_BASE_URL
        _anthropic_client = anthropic.AsyncAnthropic(**kwargs)
    return _anthropic_client


def reset_anthropic_client() -> None:
    """清除 singleton，下次呼叫 get_anthropic_client() 會重建。主要供測試使用。"""
    global _anthropic_client
    _anthropic_client = None

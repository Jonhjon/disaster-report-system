"""輕量 in-memory rate limiter（sliding window）。

用於 GET /api/chat/session/{token} 這類公開 endpoint，避免 session_token 被暴力嘗試。
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Deque

from fastapi import HTTPException, Request


class InMemoryRateLimiter:
    """Sliding window rate limiter：每個 key 維持 deque 存最近請求時間。"""

    def __init__(self, max_requests: int = 10, window_seconds: float = 60.0) -> None:
        self._max_requests = max_requests
        self._window = window_seconds
        self._history: dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def configure(self, max_requests: int, window_seconds: float) -> None:
        with self._lock:
            self._max_requests = max_requests
            self._window = window_seconds
            self._history.clear()

    def reset(self) -> None:
        with self._lock:
            self._history.clear()

    def hit(self, key: str) -> None:
        """紀錄一次請求；若超過上限 raise HTTPException(429)。"""
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            bucket = self._history[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self._max_requests:
                retry_after = max(1, int(bucket[0] + self._window - now))
                raise HTTPException(
                    status_code=429,
                    detail="請求過於頻繁，請稍後再試",
                    headers={"Retry-After": str(retry_after)},
                )
            bucket.append(now)


session_token_rate_limiter = InMemoryRateLimiter(max_requests=10, window_seconds=60.0)


def enforce_session_token_rate_limit(request: Request) -> None:
    """FastAPI dependency：以來源 IP 為 key 套用 rate limit。"""
    client = request.client
    key = client.host if client else "unknown"
    session_token_rate_limiter.hit(key)

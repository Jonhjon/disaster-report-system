"""M-1：LLM 串流失敗時應 db.rollback()，避免 dirty transaction 留在 pool。

已 flush 但未 commit 的 ChatMessage、DisasterEvent 變更若不 rollback，
連線歸還 pool 後下次使用者可能拿到髒狀態。
"""
from __future__ import annotations

import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app


@pytest.fixture(autouse=True)
def _reset_sse_app_status():
    from sse_starlette.sse import AppStatus

    AppStatus.should_exit_event = None
    yield
    AppStatus.should_exit_event = None


def _make_session(token):
    s = MagicMock()
    s.id = uuid4()
    s.session_token = token
    s.event_id = None
    s.messages = []
    s.pending_questions = []
    s.status = "awaiting_user"
    s.last_active_at = datetime.now(timezone.utc)
    return s


def _patch_db_returns(mock_db, session_obj):
    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = session_obj
    mock_db.query.return_value = q


def test_chat_stream_error_calls_rollback_without_token():
    """stream_chat 拋例外 → db.rollback() 必被呼叫；無 session_token 路徑。"""
    mock_db = MagicMock()

    async def broken_stream(messages, **_kwargs):
        yield {"type": "text", "content": "開始處理"}
        raise RuntimeError("LLM backend exploded")

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        with patch(
            "app.api.chat.llm_service.stream_chat", side_effect=broken_stream
        ):
            with TestClient(app) as client:
                r = client.post(
                    "/api/chat",
                    json={"message": "淹水", "history": []},
                )
        assert r.status_code == 200
        # SSE 流正常結束（即使中途錯誤，也要以 error event 回 client）
        assert "error" in r.text
    finally:
        app.dependency_overrides.clear()

    assert mock_db.rollback.called, "LLM 錯誤時必須呼叫 db.rollback() 以清空 transaction"


def test_chat_stream_error_calls_rollback_with_token():
    """帶 session_token 時，stream 失敗同樣需 rollback。"""
    token = uuid4()
    stored_session = _make_session(token)
    mock_db = MagicMock()
    _patch_db_returns(mock_db, stored_session)

    async def broken_stream(messages, **_kwargs):
        yield {"type": "text", "content": "..."}
        raise RuntimeError("boom")

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        with patch(
            "app.api.chat.llm_service.stream_chat", side_effect=broken_stream
        ):
            with TestClient(app) as client:
                r = client.post(
                    "/api/chat",
                    json={
                        "message": "補資料",
                        "history": [],
                        "session_token": str(token),
                    },
                )
        assert r.status_code == 200
    finally:
        app.dependency_overrides.clear()

    assert mock_db.rollback.called

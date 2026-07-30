"""L-2：/health 與 /readiness endpoint。

/health：永遠回 200 ok（liveness）。
/readiness：測 DB 連線；若 DB 不可用回 503（K8s readiness probe 用）。
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app


def test_health_returns_ok():
    with TestClient(app) as client:
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_readiness_ok_when_db_works():
    mock_db = MagicMock()
    mock_db.execute.return_value = MagicMock()

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        with TestClient(app) as client:
            r = client.get("/readiness")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json() == {"status": "ready"}
    # 應實際呼叫 DB 驗證可達性
    assert mock_db.execute.called


def test_readiness_503_when_db_down():
    """db.execute 失敗 → readiness 應回 503，不洩漏 DB 細節。"""
    mock_db = MagicMock()
    mock_db.execute.side_effect = RuntimeError("connection refused")

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        with TestClient(app) as client:
            r = client.get("/readiness")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 503
    body = r.json()
    assert body.get("status") == "not_ready"

import os
import sys
from pathlib import Path

# 把 backend 目錄加入 Python 路徑，讓測試能找到 app 模組
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# 提前設定測試環境變數，必須在 `from app.config import settings` 之前執行，
# 否則 Settings 實例化時會因缺少 JWT_SECRET_KEY 而報錯。
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-" + "x" * 40)

from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.database import get_db, get_statistics_db
from app.main import app
from app.schemas.event import EventResponse
from app.api.deps import get_authenticated_statistics_db, get_current_user
from app.models.user import User
from app.services.auth_service import create_access_token


@pytest.fixture(autouse=True)
def _reset_anthropic_client():
    """每個測試前後重置 Anthropic client singleton，避免 monkeypatch 失效或跨測試汙染。"""
    from app.services.api_clients import reset_anthropic_client

    reset_anthropic_client()
    yield
    reset_anthropic_client()


@pytest.fixture
def event_id():
    return uuid4()


@pytest.fixture
def fake_event(event_id):
    return EventResponse(
        id=event_id,
        title="測試地震事件",
        disaster_type="earthquake",
        severity=3,
        description="芮氏規模5.0地震",
        location_text="台北市信義區",
        latitude=25.033,
        longitude=121.565,
        occurred_at=datetime.now(timezone.utc),
        casualties=0,
        injured=2,
        trapped=0,
        status="reported",
        report_count=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def test_user():
    """建立測試用的 User 物件"""
    return User(
        id=uuid4(),
        username="testadmin",
        hashed_password="fakehash",
        display_name="測試管理員",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def client(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_statistics_db] = lambda: mock_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_client(mock_db, test_user):
    """帶認證的 TestClient，override get_current_user"""
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_statistics_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_authenticated_statistics_db] = lambda: mock_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    """產生有效的 JWT Authorization header"""
    token = create_access_token({"sub": "testadmin"})
    return {"Authorization": f"Bearer {token}"}


def resolve_atomic(attr_value, original: int):
    """在測試中解析 SQL atomic increment 表達式。

    _merge_into_event 對 report_count / casualties 等欄位使用
    `DisasterEvent.col + delta`（BinaryExpression），真實 flush 後才會變 int。
    測試用 MagicMock 時沒有 flush，此 helper 模擬該表達式對原值的作用，
    讓測試能以 int 比對。
    """
    from sqlalchemy.sql.elements import BinaryExpression

    if not isinstance(attr_value, BinaryExpression):
        return attr_value
    right = attr_value.right
    delta = getattr(right, "value", None)
    if delta is None:
        delta = int(str(right))
    op = attr_value.operator.__name__
    if op == "add":
        return original + delta
    if op == "sub":
        return original - delta
    raise ValueError(f"unsupported op: {op}")

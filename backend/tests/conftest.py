import sys
from pathlib import Path

# 把 backend 目錄加入 Python 路徑，讓測試能找到 app 模組
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.schemas.event import EventResponse


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
def client(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

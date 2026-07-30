"""上傳 API 整合測試。

涵蓋：
- 成功上傳 JPEG / PNG / WebP
- 415：不支援的 MIME / 副檔名
- 413：超過 5MB
- 422：缺檔欄
- 429：超過速率限制
"""
import io
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.api import uploads as uploads_module


# 5MB + 1 byte，用來測 413
_TOO_LARGE = 5 * 1024 * 1024 + 1


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    """把上傳目錄導向臨時資料夾，避免測試汙染 repo。"""
    monkeypatch.setattr(uploads_module, "UPLOAD_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def db_session():
    """蒐集 add 的 ReportAttachment instance 以供斷言。"""
    session = MagicMock()
    session.added = []

    def _add(obj):
        session.added.append(obj)

    def _refresh(obj):
        # 模擬 commit 後 server_default=gen_random_uuid() 賦值
        import uuid

        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()

    session.add.side_effect = _add
    session.refresh.side_effect = _refresh
    return session


@pytest.fixture
def client(db_session, monkeypatch):
    """整合 TestClient，注入 mock DB 與獨立的速率限制器。"""
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app

    # 每個測試獨立 limiter，避免互相污染
    monkeypatch.setattr(
        uploads_module, "_rate_limiter", uploads_module.RateLimiter(20, 60)
    )

    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _files(name: str, content: bytes, content_type: str) -> dict:
    return {"file": (name, io.BytesIO(content), content_type)}


# ---------------------------------------------------------------------------
# 成功路徑
# ---------------------------------------------------------------------------


def test_upload_jpeg_success(client, upload_dir, db_session):
    resp = client.post(
        "/api/uploads/photo",
        files=_files("photo.jpg", b"\xff\xd8\xff\xe0fake", "image/jpeg"),
    )

    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body
    assert body["url"].startswith("/static/uploads/reports/")
    assert body["original_filename"] == "photo.jpg"
    assert body["content_type"] == "image/jpeg"
    assert body["size_bytes"] == len(b"\xff\xd8\xff\xe0fake")

    # DB 有寫入 + 實體檔案存在
    assert len(db_session.added) == 1
    saved = list(upload_dir.iterdir())
    assert len(saved) == 1


def test_upload_png_success(client, upload_dir):
    resp = client.post(
        "/api/uploads/photo",
        files=_files("a.png", b"\x89PNG\r\n", "image/png"),
    )
    assert resp.status_code == 201


def test_upload_webp_success(client, upload_dir):
    resp = client.post(
        "/api/uploads/photo",
        files=_files("a.webp", b"RIFFxxxxWEBP", "image/webp"),
    )
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# 失敗路徑
# ---------------------------------------------------------------------------


def test_upload_rejects_pdf(client, upload_dir, db_session):
    resp = client.post(
        "/api/uploads/photo",
        files=_files("doc.pdf", b"%PDF-1.4 fake", "application/pdf"),
    )

    assert resp.status_code == 415
    # 不應有任何 DB 寫入 / 實體檔案
    assert db_session.added == []
    assert list(upload_dir.iterdir()) == []


def test_upload_rejects_oversized(client, upload_dir, db_session):
    payload = b"x" * _TOO_LARGE
    resp = client.post(
        "/api/uploads/photo",
        files=_files("big.jpg", payload, "image/jpeg"),
    )

    assert resp.status_code == 413
    assert db_session.added == []
    assert list(upload_dir.iterdir()) == []


def test_upload_missing_file_returns_422(client):
    resp = client.post("/api/uploads/photo")
    assert resp.status_code == 422


def test_upload_rate_limit(client, upload_dir, monkeypatch):
    """超過 20 次/分鐘應回 429。"""
    monkeypatch.setattr(
        uploads_module, "_rate_limiter", uploads_module.RateLimiter(3, 60)
    )

    for _ in range(3):
        resp = client.post(
            "/api/uploads/photo",
            files=_files("a.jpg", b"\xff\xd8\xff", "image/jpeg"),
        )
        assert resp.status_code == 201

    resp = client.post(
        "/api/uploads/photo",
        files=_files("a.jpg", b"\xff\xd8\xff", "image/jpeg"),
    )
    assert resp.status_code == 429

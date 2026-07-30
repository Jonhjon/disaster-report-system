"""孤兒附件清理服務測試。

驗證 cleanup_orphan_attachments：
- 24h 內未綁定的不清
- 25h 前未綁定的會清（DB row + 實體檔案）
- 已綁定的（report_id IS NOT NULL）無論多舊都不清
- 實體檔不存在時仍能刪 DB row 並 log warning
"""
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.models.report_attachment import ReportAttachment
from app.services import attachment_cleanup as svc


def _make_attachment(
    *,
    created_at: datetime,
    report_id=None,
    filename: str | None = None,
    size_bytes: int = 1024,
) -> ReportAttachment:
    a = ReportAttachment(
        filename=filename or f"{uuid.uuid4().hex}.jpg",
        original_filename="photo.jpg",
        content_type="image/jpeg",
        size_bytes=size_bytes,
    )
    a.id = uuid.uuid4()
    a.report_id = report_id
    a.created_at = created_at
    return a


def _mock_db_returning(orphans: list[ReportAttachment]) -> MagicMock:
    """db.query(...).filter(...).all() 回 orphans。"""
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = orphans
    return db


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "UPLOAD_DIR", tmp_path)
    return tmp_path


def _create_file(upload_dir: Path, filename: str, size: int = 1024) -> Path:
    p = upload_dir / filename
    p.write_bytes(b"x" * size)
    return p


# ---------------------------------------------------------------------------


def test_cleanup_deletes_old_orphan(upload_dir):
    """25 小時前未綁定的應被清掉：實體檔案刪除、DB row 刪除。"""
    old_orphan = _make_attachment(
        created_at=datetime.now(timezone.utc) - timedelta(hours=25),
        report_id=None,
    )
    _create_file(upload_dir, old_orphan.filename, size=2048)
    db = _mock_db_returning([old_orphan])

    deleted, freed = svc.cleanup_orphan_attachments(db, older_than_hours=24)

    assert deleted == 1
    assert freed == 2048
    assert not (upload_dir / old_orphan.filename).exists()
    db.delete.assert_called_once_with(old_orphan)
    db.commit.assert_called_once()


def test_cleanup_returns_zero_when_no_orphans(upload_dir):
    db = _mock_db_returning([])

    deleted, freed = svc.cleanup_orphan_attachments(db, older_than_hours=24)

    assert deleted == 0
    assert freed == 0
    db.delete.assert_not_called()


def test_cleanup_tolerates_missing_file(upload_dir, caplog):
    """實體檔不存在時仍能刪 DB row 並 log warning，不拋例外。"""
    orphan = _make_attachment(
        created_at=datetime.now(timezone.utc) - timedelta(hours=25),
        report_id=None,
    )
    # 故意不建立檔案
    db = _mock_db_returning([orphan])

    import logging

    with caplog.at_level(logging.WARNING):
        deleted, freed = svc.cleanup_orphan_attachments(db, older_than_hours=24)

    assert deleted == 1
    assert freed == 0  # 檔不存在，視為 0 bytes 釋出
    db.delete.assert_called_once_with(orphan)


def test_cleanup_handles_multiple_orphans(upload_dir):
    o1 = _make_attachment(
        created_at=datetime.now(timezone.utc) - timedelta(hours=30),
        report_id=None,
        size_bytes=1000,
    )
    o2 = _make_attachment(
        created_at=datetime.now(timezone.utc) - timedelta(hours=100),
        report_id=None,
        size_bytes=2000,
    )
    _create_file(upload_dir, o1.filename, size=1000)
    _create_file(upload_dir, o2.filename, size=2000)
    db = _mock_db_returning([o1, o2])

    deleted, freed = svc.cleanup_orphan_attachments(db, older_than_hours=24)

    assert deleted == 2
    assert freed == 3000
    assert not (upload_dir / o1.filename).exists()
    assert not (upload_dir / o2.filename).exists()


def test_cleanup_query_filters_unbound_and_old(upload_dir, monkeypatch):
    """驗證 cleanup query 至少呼叫 db.query(ReportAttachment).filter(...)，
    不直接驗證 SQL 表達式（過於耦合）。"""
    db = _mock_db_returning([])

    svc.cleanup_orphan_attachments(db, older_than_hours=24)

    db.query.assert_called_once_with(ReportAttachment)
    db.query.return_value.filter.assert_called_once()

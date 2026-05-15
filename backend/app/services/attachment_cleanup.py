"""孤兒附件清理服務。

策略：上傳超過 N 小時但 `report_id IS NULL` 的 attachment 視為孤兒，刪 DB row +
實體檔案。實體檔案刪不掉時 log warning 但不 rollback DB（檔案孤兒比 DB 孤兒可接受）。

排程於 app.main 的 lifespan 內每小時呼叫一次。
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.report_attachment import ReportAttachment

logger = logging.getLogger(__name__)

# 模組級常數：測試可 monkeypatch；與 uploads.UPLOAD_DIR 指向同一資料夾
UPLOAD_DIR: Path = (
    Path(__file__).resolve().parents[1] / "static" / "uploads" / "reports"
)


def cleanup_orphan_attachments(
    db: Session, older_than_hours: int = 24
) -> tuple[int, int]:
    """掃描並刪除過期孤兒附件。

    Args:
        db: SQLAlchemy session
        older_than_hours: 上傳後超過幾小時仍未綁定即視為孤兒

    Returns:
        (deleted_count, freed_bytes)
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
    start = time.monotonic()

    orphans = (
        db.query(ReportAttachment)
        .filter(
            and_(
                ReportAttachment.report_id.is_(None),
                ReportAttachment.created_at < cutoff,
            )
        )
        .all()
    )

    deleted = 0
    freed = 0
    for orphan in orphans:
        path = UPLOAD_DIR / orphan.filename
        size = 0
        try:
            if path.exists():
                size = path.stat().st_size
                path.unlink()
            else:
                logger.warning(
                    "孤兒清理：實體檔不存在 attachment_id=%s filename=%s",
                    orphan.id,
                    orphan.filename,
                )
        except OSError:
            # 檔案系統錯誤不阻斷 DB 清理（避免 DB row 永遠卡住）
            logger.exception(
                "孤兒清理：刪實體檔失敗 attachment_id=%s", orphan.id
            )

        db.delete(orphan)
        deleted += 1
        freed += size

    if deleted:
        db.commit()
        elapsed = time.monotonic() - start
        logger.info(
            "孤兒清理完成：刪 %d 筆、釋出 %d bytes、耗時 %.2fs",
            deleted,
            freed,
            elapsed,
        )

    return deleted, freed

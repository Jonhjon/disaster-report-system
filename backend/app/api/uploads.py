"""民眾通報照片上傳 API。

兩階段流程：
1. 民眾於聊天介面選照片 → POST /api/uploads/photo（multipart）→ 取得 attachment_id + url
2. 民眾送出對話時把 attachment_ids 帶在 ChatRequest，後端在建立 DisasterReport 時綁定

未綁定的 attachment 由 services.attachment_cleanup 排程清理（24h 保留窗）。
"""
from __future__ import annotations

import logging
import time
import uuid
from collections import deque
from pathlib import Path
from threading import Lock

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.report_attachment import ReportAttachment
from app.models.user import User
from app.schemas.attachment import AttachmentOut
from app.services import attachment_cleanup

logger = logging.getLogger(__name__)

router = APIRouter()


# 模組級常數：測試可 monkeypatch 改成 tmp_path
UPLOAD_DIR: Path = (
    Path(__file__).resolve().parents[1] / "static" / "uploads" / "reports"
)

ALLOWED_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
ALLOWED_EXTENSIONS: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_BYTES = 5 * 1024 * 1024  # 5 MB


class RateLimiter:
    """簡單的固定視窗 in-memory 限流器（每 client 每視窗 max_requests 次）。

    單實例部署足夠；多實例需改用 Redis 或 Postgres advisory lock。
    """

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()

    def check(self, client_id: str) -> bool:
        """回傳 True 代表允許；False 代表超限。"""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = self._hits.setdefault(client_id, deque())
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_requests:
                return False
            bucket.append(now)
            return True


# 每 IP 每分鐘 20 次（防灌爆）
_rate_limiter = RateLimiter(max_requests=20, window_seconds=60)


def _client_id(request: Request) -> str:
    # 反向代理場景可改成讀 X-Forwarded-For，目前直接用 remote address
    return request.client.host if request.client else "anonymous"


@router.post(
    "/uploads/photo",
    response_model=AttachmentOut,
    status_code=status.HTTP_201_CREATED,
)
def upload_photo(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> AttachmentOut:
    """接收單張照片，存到本地並寫入 report_attachments（report_id=NULL）。"""

    if not _rate_limiter.check(_client_id(request)):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="上傳次數過於頻繁，請稍後再試",
        )

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"僅支援 JPEG / PNG / WebP，收到 {file.content_type}",
        )

    # 讀進 memory 後檢查大小：上限 5MB 不會撐爆，但仍須避免 client 灌大檔
    content = file.file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"檔案大小超過 {MAX_BYTES // (1024 * 1024)} MB 上限",
        )

    ext = ALLOWED_EXTENSIONS[file.content_type]
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / filename
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    try:
        dest.write_bytes(content)
    except OSError:
        logger.exception("寫入上傳檔案失敗 dest=%s", dest)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="儲存檔案失敗",
        )

    attachment = ReportAttachment(
        filename=filename,
        original_filename=file.filename or filename,
        content_type=file.content_type,
        size_bytes=len(content),
    )
    try:
        db.add(attachment)
        db.commit()
        db.refresh(attachment)
    except Exception:
        # DB 失敗時要把實體檔案刪掉避免孤兒（理論上不會發生，但保險）
        logger.exception("寫入 report_attachments 失敗")
        dest.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="儲存附件 metadata 失敗",
        )

    return AttachmentOut(
        id=attachment.id,
        url=f"/static/uploads/reports/{filename}",
        original_filename=attachment.original_filename,
        content_type=attachment.content_type,
        size_bytes=attachment.size_bytes,
    )


@router.post("/uploads/cleanup-orphans")
def trigger_cleanup_orphans(
    older_than_hours: int = 24,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    """管理員手動觸發孤兒附件清理（debug / 緊急用）。"""
    deleted, freed = attachment_cleanup.cleanup_orphan_attachments(
        db, older_than_hours=older_than_hours
    )
    return {"deleted_count": deleted, "freed_bytes": freed}

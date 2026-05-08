"""Liveness / Readiness probe endpoints。

/health：永遠回 200（liveness probe；process 活著就算過）。
/readiness：跑一次 SELECT 1 驗證 DB；DB 掛了回 503，讓 orchestrator 停導流量。
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter(tags=["Health"])
logger = logging.getLogger(__name__)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readiness")
def readiness(response: Response, db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("readiness probe failed: %s", exc)
        response.status_code = 503
        return {"status": "not_ready"}
    return {"status": "ready"}

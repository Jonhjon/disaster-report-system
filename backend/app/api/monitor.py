from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.llm_log import LLMLog
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/llm-logs")
def get_llm_logs(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    logs = (
        db.query(LLMLog)
        .order_by(LLMLog.timestamp.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": str(log.id),
            "timestamp": log.timestamp.isoformat(),
            "model": log.model,
            "latency_ms": log.latency_ms,
            "token_usage": {
                "input_tokens": log.input_tokens,
                "output_tokens": log.output_tokens,
                "total_tokens": log.total_tokens,
            },
            "status": log.status,
            "prompt": log.prompt,
            "output": log.output,
        }
        for log in logs
    ]

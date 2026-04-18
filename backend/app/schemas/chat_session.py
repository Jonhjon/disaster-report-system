from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class PendingQuestion(BaseModel):
    id: str
    question: str
    asked_by: str
    asked_at: datetime


class ChatSessionPublic(BaseModel):
    session_token: UUID
    status: str
    messages: list[dict[str, Any]]
    pending_questions: list[PendingQuestion]
    event_id: UUID | None = None

    model_config = {"from_attributes": True}

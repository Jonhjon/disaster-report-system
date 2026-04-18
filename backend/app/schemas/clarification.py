from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ClarificationCreate(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    channel: Literal["sms", "line", "email"]
    recipient: str | None = None


class ClarificationResponse(BaseModel):
    id: UUID
    channel: str
    status: str
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    replied_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

from uuid import UUID

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    session_token: UUID | None = None
    history: list[ChatMessage] = []

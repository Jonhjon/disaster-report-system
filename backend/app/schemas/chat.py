from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str = Field(..., max_length=8000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: str | None = None
    history: list[ChatMessage] = Field(default=[], max_length=50)

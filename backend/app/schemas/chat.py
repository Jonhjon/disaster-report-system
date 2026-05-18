from uuid import UUID

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str = Field(..., max_length=8000)


class DeviceLocation(BaseModel):
    """行動裝置 GPS 取得的位置（選填）。

    座標可作為 LLM 推測地點時的提示，但仍需向使用者確認具體地址。
    """

    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: str | None = None
    history: list[ChatMessage] = Field(default=[], max_length=50)
    attachment_ids: list[UUID] = Field(default=[], max_length=3)
    # 行動 App 透過 Phone Number Hint API 取得並由系統驗證的電話號碼。
    # 若有此值，後端會覆寫 LLM 填入的 reporter_phone，並在 system prompt
    # 告知 LLM 不要再向使用者詢問電話。
    verified_phone: str | None = Field(default=None, max_length=32)
    # 行動 App 取得的 GPS 位置（選填）。
    device_location: DeviceLocation | None = None

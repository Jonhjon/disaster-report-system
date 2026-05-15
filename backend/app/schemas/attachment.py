from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AttachmentOut(BaseModel):
    """民眾通報附件（照片）對外輸出 schema。

    url 為相對路徑（/static/...），前端可直接使用同源請求；若部署於不同 origin，
    由前端 BASE_URL 拼接完整網址即可。
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    original_filename: str
    content_type: str
    size_bytes: int

from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


DisasterTypeEnum = Literal[
    "trapped",
    "road_collapse",
    "flooding",
    "landslide",
    "small_landslide",
    "building_damage",
    "utility_damage",
    "fire",
    "other",
]


class SubmitDisasterReportPayload(BaseModel):
    disaster_type: DisasterTypeEnum
    description: str
    location_text: str
    severity: int = Field(..., ge=1, le=5)
    casualties: int = Field(0, ge=0)
    injured: int = Field(0, ge=0)
    severe_injured: int = Field(0, ge=0)
    trapped: int = Field(0, ge=0)
    occurred_at: Optional[str] = None
    merge_event_id: Optional[str] = None
    reporter_name: str
    reporter_phone: str

    model_config = {"extra": "ignore"}

    @model_validator(mode="after")
    def clamp_severe_injured(self) -> "SubmitDisasterReportPayload":
        # 重傷是受傷子集：LLM 若誤報超過受傷總數，夾擠而非讓整筆通報失敗
        if self.severe_injured > self.injured:
            self.severe_injured = self.injured
        return self

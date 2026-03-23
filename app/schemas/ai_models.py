from pydantic import BaseModel, Field
from typing import Literal

class AIAnalysisResult(BaseModel):
    is_relevant: bool = Field(default=False)
    rejection_reason: str = Field(default="")
    identification: str = Field(default="")
    solution: str = Field(default="")
    diy_feasibility: Literal["EASY", "MEDIUM", "HARD", "DO_NOT_ATTEMPT", "UNKNOWN"] = Field(default="UNKNOWN")
    dangers: str = Field(default="")
    confidence: float = Field(default=1.0)
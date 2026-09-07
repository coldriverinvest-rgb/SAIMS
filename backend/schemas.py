from typing import Literal
from pydantic import BaseModel, Field

class AIResult(BaseModel):
    summary_points: list[str] = Field(min_length=3, max_length=3)
    sentiment: Literal["기회", "주의", "중립"]
    priority: Literal["HIGH", "MID", "LOW"]
    strategic_implication: str
    business_impact: str = "사업 및 밸류체인 영향 검토가 필요합니다."
    keyword_tags: list[str] = []
    key_figures: list[dict[str, str]] = []

class AnalyzeRequest(BaseModel):
    title: str
    text: str = ""
    group_type: str = "경쟁사"
    rcept_no: str | None = None

class TelegramRequest(BaseModel):
    title: str
    corp_name: str
    ai_result: AIResult
    source_url: str = ""

class RecipientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    chat_id: str = Field(default="", max_length=80)
    email: str = Field(default="", max_length=254)
    telegram_enabled: bool = True
    email_enabled: bool = True

class RecipientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    enabled: bool | None = None
    chat_id: str | None = Field(default=None, max_length=80)
    email: str | None = Field(default=None, max_length=254)
    telegram_enabled: bool | None = None
    email_enabled: bool | None = None

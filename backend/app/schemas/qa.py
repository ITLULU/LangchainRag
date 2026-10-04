from pydantic import BaseModel, Field
from typing import Optional, List


class AskRequest(BaseModel):
    """问答请求（简化 API）"""
    channel: str = Field(..., description="employee_kb 或 cs_agent")
    question: str = Field(..., min_length=1, max_length=5000)
    conversation_id: Optional[str] = None
    kb_ids: Optional[List[str]] = None  # 指定KB范围（可选）
    stream: bool = True


class ChatCompletionRequest(BaseModel):
    """OpenAI 兼容问答请求"""
    model: str = "qwen-plus"
    messages: List[dict]
    channel: str = "employee_kb"
    conversation_id: Optional[str] = None
    kb_ids: Optional[List[str]] = None
    stream: bool = True
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class Citation(BaseModel):
    no: int
    doc: str
    page: int
    snippet: str
    score: float


class AskResponse(BaseModel):
    """非流式问答响应"""
    answer: str
    citations: List[Citation] = []
    confidence: Optional[float] = None
    refused: bool = False
    handoff: bool = False
    trace_id: str
    conversation_id: str


class ConversationOut(BaseModel):
    id: str
    channel: str
    title: Optional[str]
    created_at: str
    message_count: int = 0

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    id: str
    conv_id: str
    role: str
    content_masked: str
    citations: Optional[str]
    confidence: Optional[float]
    refused: bool
    handoff: bool
    created_at: str

    class Config:
        from_attributes = True


class FeedbackCreate(BaseModel):
    query_log_id: str
    rating: str = Field(..., pattern="^(up|down)$")
    reason: Optional[str] = None


class QueryLogOut(BaseModel):
    id: str
    trace_id: str
    user_id: str
    channel: str
    question_masked: str
    confidence: Optional[float]
    refused: bool
    handoff: bool
    latency_ms: int
    cost: float
    created_at: str

    class Config:
        from_attributes = True


class DashboardStats(BaseModel):
    total_kbs: int = 0
    total_docs: int = 0
    total_queries: int = 0
    avg_confidence: float = 0.0
    reject_rate: float = 0.0
    self_service_rate: float = 0.0
    daily_queries: List[dict] = []
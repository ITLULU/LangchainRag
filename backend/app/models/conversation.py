"""会话、消息、问答日志、反馈模型"""
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Float, Text, Boolean, func, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class Conversation(Base):
    __tablename__ = "conversation"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    external_uid_masked: Mapped[str] = mapped_column(String(200), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expire_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


class Message(Base):
    __tablename__ = "message"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conv_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user / assistant
    content_masked: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[str] = mapped_column(Text, nullable=True)  # JSON
    confidence: Mapped[float] = mapped_column(Float, nullable=True)
    refused: Mapped[bool] = mapped_column(Boolean, default=False)
    handoff: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class QueryLog(Base):
    """问答日志（审计用）"""
    __tablename__ = "query_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    question_masked: Mapped[str] = mapped_column(Text, nullable=False)
    answer_masked: Mapped[str] = mapped_column(Text, nullable=True)
    kb_ids: Mapped[str] = mapped_column(Text, nullable=True)  # JSON
    collection_hits: Mapped[str] = mapped_column(Text, nullable=True)
    citations: Mapped[str] = mapped_column(Text, nullable=True)  # JSON
    confidence: Mapped[float] = mapped_column(Float, nullable=True)
    refused: Mapped[bool] = mapped_column(Boolean, default=False)
    handoff: Mapped[bool] = mapped_column(Boolean, default=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    query_log_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    rating: Mapped[str] = mapped_column(String(10), nullable=False)  # up / down
    reason: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
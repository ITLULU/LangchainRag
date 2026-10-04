"""知识库与授权模型"""
import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import String, DateTime, Enum as SAEnum, Boolean, Float, Text, func, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class ChannelType(str, Enum):
    EMPLOYEE_KB = "employee_kb"   # 通道A：企业员工手册
    CS_AGENT = "cs_agent"         # 通道B：智能客服


class Visibility(str, Enum):
    PUBLIC = "public"      # 全员可见
    DEPT = "dept"          # 部门可见
    ROLE = "role"          # 角色可见


class KnowledgeBase(Base):
    """知识库元数据表，每个KB绑定一个Chroma/Qdrant collection"""
    __tablename__ = "knowledge_base"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    channel_type: Mapped[ChannelType] = mapped_column(
        SAEnum(ChannelType), default=ChannelType.EMPLOYEE_KB, nullable=False, index=True
    )
    collection_name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    owner_dept: Mapped[str] = mapped_column(String(200), nullable=False, default="通用部门")
    visibility: Mapped[Visibility] = mapped_column(
        SAEnum(Visibility), default=Visibility.PUBLIC, nullable=False
    )
    # 切分配置
    chunk_size: Mapped[int] = mapped_column(default=800)
    chunk_overlap: Mapped[int] = mapped_column(default=150)
    split_strategy: Mapped[str] = mapped_column(String(50), default="chinese_paragraph")
    table_strategy: Mapped[str] = mapped_column(String(50), default="llm_to_text")
    # 问答配置
    reject_threshold: Mapped[float] = mapped_column(Float, default=0.35)
    top_k_override: Mapped[int] = mapped_column(default=5)
    temperature: Mapped[float] = mapped_column(Float, default=0.1)
    prompt_template: Mapped[str] = mapped_column(Text, nullable=True)
    # 状态
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    doc_count: Mapped[int] = mapped_column(default=0)
    chunk_count: Mapped[int] = mapped_column(default=0)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_kb_channel_status", "channel_type", "status"),
    )


class KbGrant(Base):
    """知识库授权表（第一层权限过滤）"""
    __tablename__ = "kb_grant"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kb_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    grantee_type: Mapped[str] = mapped_column(String(20), nullable=False)  # dept / role / user
    grantee_id: Mapped[str] = mapped_column(String(100), nullable=False)
    can_read: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_kb_grant_kb", "kb_id", "grantee_type", "grantee_id"),
    )
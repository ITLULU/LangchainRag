"""文档、版本、切片、入库任务模型"""
import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import String, DateTime, Enum as SAEnum, Boolean, Integer, Float, Text, func, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class SecurityLevel(str, Enum):
    PUBLIC = "公开"
    INTERNAL = "内部"
    CONFIDENTIAL = "机密"


class Document(Base):
    __tablename__ = "document"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kb_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    author: Mapped[str] = mapped_column(String(100), nullable=True)
    dept: Mapped[str] = mapped_column(String(200), nullable=True)
    security_level: Mapped[SecurityLevel] = mapped_column(
        SAEnum(SecurityLevel), default=SecurityLevel.PUBLIC, nullable=False
    )
    effective_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    expiry_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    tags: Mapped[str] = mapped_column(String(500), nullable=True)  # JSON array string
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class DocVersion(Base):
    __tablename__ = "doc_version"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    doc_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    oss_file_key: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)  # bytes
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    index_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    error_msg: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_doc_version_doc", "doc_id", "version", unique=True),
    )


class ChunkMeta(Base):
    """切片元信息（MySQL存索引，向量本体在Chroma/Qdrant）"""
    __tablename__ = "chunk_meta"

    id: Mapped[str] = mapped_column(String(200), primary_key=True)  # doc_id:ver:idx
    doc_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_no: Mapped[int] = mapped_column(Integer, default=0)
    token_len: Mapped[int] = mapped_column(Integer, default=0)
    vector_id: Mapped[str] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class IngestTask(Base):
    """入库任务"""
    __tablename__ = "ingest_task"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doc_version_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    cost_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, nullable=True)
    retry_cnt: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
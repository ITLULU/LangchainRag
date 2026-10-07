from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.models.document import SecurityLevel


class DocumentCreate(BaseModel):
    kb_id: str
    title: str = Field(..., min_length=1, max_length=500)
    author: Optional[str] = None
    dept: Optional[str] = None
    security_level: SecurityLevel = SecurityLevel.PUBLIC
    tags: Optional[str] = None  # comma-separated or JSON


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    security_level: Optional[SecurityLevel] = None
    tags: Optional[str] = None
    status: Optional[str] = None
    effective_date: Optional[str] = None
    expiry_date: Optional[str] = None


class DocumentOut(BaseModel):
    id: str
    kb_id: str
    title: str
    author: Optional[str]
    dept: Optional[str]
    security_level: SecurityLevel
    effective_date: Optional[datetime]
    expiry_date: Optional[datetime]
    tags: Optional[str]
    current_version: int
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocVersionOut(BaseModel):
    id: str
    doc_id: str
    version: int
    file_type: str
    file_size: int
    page_count: int
    index_status: str
    chunk_count: int
    error_msg: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class IngestTaskOut(BaseModel):
    id: str
    doc_version_id: str
    status: str
    progress: float
    chunk_count: int
    cost_ms: int
    error: Optional[str]
    retry_cnt: int
    created_at: datetime

    class Config:
        from_attributes = True


class ChunkPreviewRequest(BaseModel):
    doc_id: str
    chunk_size: Optional[int] = 800
    chunk_overlap: Optional[int] = 150


class ChunkPreviewItem(BaseModel):
    index: int
    content: str
    token_count: int
    page_no: int


class ChunkPreviewOut(BaseModel):
    doc_id: str
    total_chunks: int
    chunks: list[ChunkPreviewItem]
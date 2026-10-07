from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.models.kb import ChannelType, Visibility


class KBCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    channel_type: ChannelType = ChannelType.EMPLOYEE_KB
    owner_dept: str = "通用部门"
    visibility: Visibility = Visibility.PUBLIC
    chunk_size: int = Field(default=800, ge=200, le=4000)
    chunk_overlap: int = Field(default=150, ge=0, le=1000)
    split_strategy: str = "chinese_paragraph"
    table_strategy: str = "llm_to_text"
    reject_threshold: float = Field(default=0.35, ge=0.0, le=1.0)
    top_k_override: int = Field(default=5, ge=1, le=20)
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    prompt_template: Optional[str] = None


class KBUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    visibility: Optional[Visibility] = None
    chunk_size: Optional[int] = Field(default=None, ge=200, le=4000)
    chunk_overlap: Optional[int] = Field(default=None, ge=0, le=1000)
    reject_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    top_k_override: Optional[int] = Field(default=None, ge=1, le=20)
    temperature: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    prompt_template: Optional[str] = None
    status: Optional[str] = None


class KBOut(BaseModel):
    id: str
    name: str
    description: Optional[str]
    channel_type: ChannelType
    collection_name: str
    owner_dept: str
    visibility: Visibility
    chunk_size: int
    chunk_overlap: int
    split_strategy: str
    reject_threshold: float
    top_k_override: int
    temperature: float
    prompt_template: Optional[str]
    status: str
    doc_count: int
    chunk_count: int
    created_by: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KbGrantCreate(BaseModel):
    kb_id: str
    grantee_type: str  # dept / role / user
    grantee_id: str
    can_read: bool = True


class KbGrantOut(BaseModel):
    id: str
    kb_id: str
    grantee_type: str
    grantee_id: str
    can_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel):
    items: List
    total: int
    page: int
    page_size: int
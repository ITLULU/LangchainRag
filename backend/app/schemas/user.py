from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.models.user import UserRole, UserSecurityLevel


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=4)
    display_name: str
    email: Optional[str] = None
    department: str = "通用部门"
    role: UserRole = UserRole.EMPLOYEE
    security_level: UserSecurityLevel = UserSecurityLevel.INTERNAL


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: str
    username: str
    display_name: str
    email: Optional[str]
    department: str
    role: UserRole
    security_level: UserSecurityLevel
    is_active: bool
    channel_scope: str
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class RefreshRequest(BaseModel):
    refresh_token: str
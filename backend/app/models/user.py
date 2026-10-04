"""用户、角色、权限模型"""
import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import String, DateTime, Enum as SAEnum, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class UserRole(str, Enum):
    """6 内置角色"""
    PLATFORM_ADMIN = "platform_admin"       # 平台管理员
    KB_ADMIN = "kb_admin"                   # 知识管理员
    DEPT_ADMIN = "dept_admin"               # 部门管理员
    EMPLOYEE = "employee"                   # 内部员工
    CS_AGENT = "cs_agent"                   # 客服坐席
    CUSTOMER = "customer"                   # C端客户


class UserSecurityLevel(str, Enum):
    PUBLIC = "公开"
    INTERNAL = "内部"
    CONFIDENTIAL = "机密"


class User(Base):
    __tablename__ = "user"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(200), nullable=True)
    department: Mapped[str] = mapped_column(String(200), nullable=False, default="通用部门")
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.EMPLOYEE, nullable=False)
    security_level: Mapped[UserSecurityLevel] = mapped_column(
        SAEnum(UserSecurityLevel), default=UserSecurityLevel.INTERNAL, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_disabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    channel_scope: Mapped[str] = mapped_column(String(50), default="employee_kb", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
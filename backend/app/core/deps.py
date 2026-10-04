"""FastAPI 依赖注入：当前用户、数据库会话"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.security import decode_token
from app.models.user import User

security_scheme = HTTPBearer(auto_error=False)


class CurrentUser:
    """当前用户信息载体"""
    def __init__(self, payload: dict, user: Optional[User] = None):
        self.id = payload.get("sub")
        self.username = payload.get("username", "")
        self.role = payload.get("role", "")
        self.security_level = payload.get("security_level", "公开")
        self.department = payload.get("department", "")
        self.channel_scope = payload.get("channel_scope", "employee_kb")
        self._user = user

    @property
    def is_authenticated(self) -> bool:
        return self.id is not None

    @property
    def is_admin(self) -> bool:
        return self.role in ("platform_admin", "kb_admin")


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """解析 JWT 获取当前用户"""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")

    try:
        payload = decode_token(credentials.credentials)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token 无效或已过期")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token 无效")

    # 查DB确认用户存在且未被禁用
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active or user.is_disabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户已被禁用或不存在")

    return CurrentUser(payload, user)


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[CurrentUser]:
    """可选认证——未登录不抛异常"""
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


def require_role(*roles: str):
    """角色检查依赖工厂"""
    async def role_checker(current_user: CurrentUser = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要以下角色之一: {', '.join(roles)}",
            )
        return current_user
    return role_checker
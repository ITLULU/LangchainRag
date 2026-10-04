"""认证 API——登录、注册、刷新 token"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserLogin, UserCreate, TokenResponse, RefreshRequest, UserOut
from app.core.security import (
    verify_password, hash_password,
    create_access_token, create_refresh_token, decode_token,
)
from app.core.deps import get_current_user, CurrentUser

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/register", response_model=TokenResponse)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    """用户注册"""
    # 检查用户名是否已存在
    result = await db.execute(select(User).where(User.username == data.username))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = User(
        username=data.username,
        hashed_password=hash_password(data.password),
        display_name=data.display_name,
        email=data.email,
        department=data.department,
        role=data.role,
        security_level=data.security_level,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    access_token = create_access_token(
        user.id, user.username, user.role.value, user.security_level.value,
        user.department, user.channel_scope,
    )
    refresh_token = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserOut.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    """用户登录"""
    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not user.is_active or user.is_disabled:
        raise HTTPException(status_code=403, detail="账户已被禁用")

    access_token = create_access_token(
        user.id, user.username, user.role.value, user.security_level.value,
        user.department, user.channel_scope,
    )
    refresh_token = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserOut.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """刷新 access token"""
    try:
        payload = decode_token(data.refresh_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="refresh token 无效或已过期")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="无效的 token 类型")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=403, detail="用户不可用")

    access_token = create_access_token(
        user.id, user.username, user.role.value, user.security_level.value,
        user.department, user.channel_scope,
    )
    new_refresh = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
async def get_me(current_user: CurrentUser = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return UserOut.model_validate(current_user._user)
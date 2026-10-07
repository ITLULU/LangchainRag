"""JWT 认证与密码哈希"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import bcrypt
from jose import jwt, JWTError
from app.config import get_settings

settings = get_settings()

ALGORITHM = settings.JWT_ALGORITHM
SECRET_KEY = settings.SECRET_KEY


def verify_password(plain_password: str, hashed_password: str) -> bool:
    # bcrypt 密码上限 72 字节，与 hash_password 保持一致的截断策略
    pwd = plain_password.encode("utf-8")[:72]
    try:
        return bcrypt.checkpw(pwd, hashed_password.encode("utf-8"))
    except ValueError:
        return False


def hash_password(password: str) -> str:
    # bcrypt 只接受最长 72 字节的密码
    pwd = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pwd, bcrypt.gensalt(rounds=12)).decode("utf-8")


def create_access_token(
    user_id: str,
    username: str,
    role: str,
    security_level: str,
    department: str,
    channel_scope: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """创建短期 access token (默认15分钟)"""
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.JWT_EXPIRE_MINUTES)

    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "security_level": security_level,
        "department": department,
        "channel_scope": channel_scope,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """创建 refresh token"""
    if expires_delta is None:
        expires_delta = timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)

    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """解析 JWT，返回 payload"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise ValueError("无效或过期的 token")
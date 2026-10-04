"""
AskKB 全局配置
统一管理所有环境变量与运行时参数
"""
import os
from typing import Literal, Optional
from pydantic_settings import BaseSettings
from pydantic import model_validator
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置，所有配置项均从环境变量读取"""

    # ─── 应用基础 ───
    APP_NAME: str = "AskKB"
    APP_VERSION: str = "0.9.0"
    DEBUG: bool = False
    ENVIRONMENT: Literal["dev", "test", "prod"] = "dev"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ─── 安全 ───
    SECRET_KEY: str = "askkb-dev-secret-change-in-production-k8x9m3pq"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_EXPIRE_DAYS: int = 7

    # ─── 数据库 ───
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/askkb.db"

    # ─── Redis ───
    REDIS_URL: str = "redis://localhost:6379/0"

    # ─── 阿里云百炼 / DashScope ───
    # 兼容 DASHSCOPE_API_KEY 和 DASH_SCOPE_API_KEY 两种写法
    DASHSCOPE_API_KEY: str = ""
    LLM_MODEL: str = "qwen-plus"
    EMBEDDING_MODEL: str = "text-embedding-v4"
    RERANK_MODEL: str = "gte-rerank"

    @model_validator(mode="after")
    def _resolve_api_key(self):
        """兼容 DASH_SCOPE_API_KEY 环境变量名"""
        if not self.DASHSCOPE_API_KEY:
            alt_key = os.getenv("DASH_SCOPE_API_KEY", "")
            if alt_key:
                object.__setattr__(self, "DASHSCOPE_API_KEY", alt_key)
        return self

    # ─── 向量库 (dev 用 Chroma, prod 用 Qdrant) ───
    VECTOR_STORE_TYPE: Literal["chroma", "qdrant"] = "chroma"
    CHROMA_PERSIST_DIR: str = "./data/chroma_db"
    QDRANT_URL: str = "http://localhost:6333"

    # ─── 文件存储 ───
    UPLOAD_DIR: str = "./data/uploads"
    MAX_UPLOAD_SIZE_MB: int = 50
    MAX_UPLOAD_PAGES: int = 500
    MAX_BATCH_UPLOAD_COUNT: int = 100

    # ─── 检索与问答 ───
    RETRIEVAL_TOP_N: int = 20           # 混合检索粗排召回数
    RERANK_TOP_K: int = 5               # 精排后保留数
    DEFAULT_REJECT_THRESHOLD: float = 0.35  # 默认拒答置信阈值
    CS_REJECT_THRESHOLD: float = 0.45       # 对客通道更高
    GENERATION_TIMEOUT_SEC: int = 30    # 生成超时
    RETRIEVAL_TIMEOUT_MS: int = 500     # 检索超时

    # ─── 会话记忆 ───
    CONVERSATION_TTL_HOURS: int = 24    # Redis会话TTL
    MAX_MEMORY_ROUNDS: int = 5          # 最近N轮拼接

    # ─── 限流 ───
    RATE_LIMIT_PER_MIN: int = 20        # 每用户/分钟
    CS_CHANNEL_MAX_CONCURRENT: int = 200
    EMPLOYEE_CHANNEL_MAX_CONCURRENT: int = 50

    # ─── CORS ───
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ─── Celery ───
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()